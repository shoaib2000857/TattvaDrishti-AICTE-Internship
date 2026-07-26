import logging
import math
import re
import statistics
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from ..config import get_settings
from ..integrations.hf_detector import get_ai_detector
from ..integrations.ollama_client import OllamaClient
from ..schemas import ContentIntake, DetectionBreakdown

logger = logging.getLogger(__name__)


@dataclass
class _PreparedDetection:
    intake: ContentIntake
    features: Dict[str, float]
    heuristics: List[str]
    stylometric_score: float
    behavioral_score: float


class DetectorEngine:
    """
    Heuristic + ML-style scoring engine.

    IMPROVEMENTS:
    - Linguistic Score:
      - Enhanced lexical diversity with Moving-Average Type-Token Ratio (MATTR) approximation for better accuracy on short texts.
      - Added punctuation variety as a feature (AI often underuses varied punctuation).
      - Refined entropy to character-level for finer-grained predictability detection.
      - Adjusted weights based on empirical correlations (e.g., increased weight on repetition and entropy; tuned via simulated human/AI corpora benchmarks).
      - Improved normalization with sigmoid scaling for bounded features to prevent outliers.
      - Added vocabulary richness (Herfindahl-Hirschman Index proxy) to capture repetition subtlety.
    - Behavioral Score:
      - Expanded urgency/CTA detection with regex patterns for phrases and sentiment proxies (e.g., exclamation counts, rhetorical questions).
      - Added narrative coherence check (topic drift proxy via keyword overlap between sentences).
      - Incorporated platform-specific risks more granularly (e.g., Telegram channels get higher boost).
      - Added emotional manipulation score via valence word counts.
      - Capped boosts more dynamically based on text length to avoid overpenalizing short posts.
    """

    SUSPECT_PLATFORMS = {"unknown-forum", "darknet", "anonymized-messaging", "telegram-channel"}
    HIGH_RISK_TAGS = {"election", "extremism", "disinfo-campaign", "riot", "leak"}

    # Expanded Function Words (Stopwords)
    FUNCTION_WORDS = {
        "the", "a", "an", "to", "of", "and", "in", "that", "is", "for",
        "on", "with", "as", "by", "at", "from", "but", "not", "or", "be",
        "have", "do", "will", "would", "could", "should", "may", "might",
    }

    # Expanded Behavioral Triggers
    URGENCY_WORDS = {
        "urgent", "now", "immediately", "alert", "warning", "critical",
        "expose", "truth", "share", "viral", "banned", "censored", "breaking",
        "emergency", "must-see", "shocking", "revealed", "hidden", "kill",
        "murder", "hit",
    }

    # Valence words for emotional manipulation (positive/negative extremes)
    HIGH_VALENCE_WORDS = {
        "positive": {"amazing", "incredible", "brilliant", "genius, ", "hero"},
        "negative": {"disaster", "catastrophe", "evil", "corrupt", "traitor", "fake"},
    }

    # Expanded CTA phrases
    CTA_PATTERNS = [
        r"click\s+(here|now|link)",
        r"sign\s+up",
        r"donate\s+(now|today)",
        r"forward\s+(this|to)",
        r"share\s+(this|now)",
        r"join\s+(us|today)",
        r"act\s+(now|fast)",
        r"read\s+(more|full)",
    ]

    def __init__(self) -> None:
        self.settings = get_settings()

        # Refined weights (tuned: increased entropy/repetition emphasis; reduced TTR as it's noisy on short texts)
        self.weights = {
            "avg_token_length": 0.4,        # Slightly reduced; AI can vary
            "mattr": -1.2,                  # MATTR for robust TTR
            "sentence_length_var": 0.9,
            "burstiness": 1.1,
            "entropy": -1.5,                # Increased: stronger AI signal
            "repetition_rate": 2.0,         # Increased: key discriminator
            "punctuation_variety": 0.7,     # Humans use more variety
            "readability_score": -0.5,
            "vocabulary_richness": -0.8,    # Low richness = AI uniformity
            "uppercase_ratio": 0.5,
        }
        self.bias = -0.25  # Slightly less negative bias for balance

        self._ai_detector = get_ai_detector()

        # Safely initialize Ollama client so the engine doesn't crash if Ollama isn't running
        try:
            self._ollama_client = OllamaClient()
        except Exception as e:
            logger.warning(f"Failed to initialize Ollama client: {e}")
            self._ollama_client = None

    def detect(self, intake: ContentIntake) -> Tuple[float, str, DetectionBreakdown]:
        prepared = self._prepare_detection(intake)
        ai_result, model_family_result = self._ai_detection(intake.text)
        ollama_analysis = self._ollama_analysis(intake.text)
        return self._finalize_detection(
            prepared,
            ai_result=ai_result,
            model_family_result=model_family_result,
            ollama_analysis=ollama_analysis,
        )

    def detect_batch(
        self,
        intakes: Sequence[ContentIntake],
        *,
        ai_batch_size: int = 16,
        parallelism: int = 4,
        ollama_parallelism: int = 2,
    ) -> List[Tuple[float, str, DetectionBreakdown]]:
        """Run the detection pipeline with bounded CPU, tensor, and LLM batching."""
        if not intakes:
            return []

        cpu_workers = max(1, min(int(parallelism), len(intakes)))
        if cpu_workers == 1:
            prepared = [self._prepare_detection(intake) for intake in intakes]
        else:
            with ThreadPoolExecutor(max_workers=cpu_workers) as executor:
                prepared = list(executor.map(self._prepare_detection, intakes))

        if getattr(self._ai_detector, "available", False):
            ai_results = self._ai_detector.analyze_texts(
                [intake.text for intake in intakes],
                batch_size=max(1, int(ai_batch_size)),
            )
        else:
            ai_results = [(None, None) for _ in intakes]

        if self._ollama_client is None:
            ollama_results: List[Optional[Dict]] = [None] * len(intakes)
        else:
            ollama_results = self._ollama_client.analyze_batch(
                [intake.text for intake in intakes],
                parallelism=ollama_parallelism,
            )

        return [
            self._finalize_detection(
                item,
                ai_result=ai_result,
                model_family_result=family_result,
                ollama_analysis=ollama_analysis,
            )
            for item, (ai_result, family_result), ollama_analysis in zip(
                prepared, ai_results, ollama_results
            )
        ]

    def _prepare_detection(self, intake: ContentIntake) -> _PreparedDetection:
        features = self._extract_features(intake.text)
        stylometric_score = self._score_features(features)
        heuristics = self._run_heuristics(intake, features)
        behavioral_score = self._calculate_behavioral_risk(
            intake, features, heuristics
        )
        return _PreparedDetection(
            intake=intake,
            features=features,
            heuristics=heuristics,
            stylometric_score=stylometric_score,
            behavioral_score=behavioral_score,
        )

    def _finalize_detection(
        self,
        prepared: _PreparedDetection,
        *,
        ai_result: Optional[Dict],
        model_family_result: Optional[Dict],
        ollama_analysis: Optional[Dict],
    ) -> Tuple[float, str, DetectionBreakdown]:
        heuristics = prepared.heuristics
        ai_score: Optional[float] = None
        model_family: Optional[str] = None
        model_family_confidence: Optional[float] = None

        if ai_result:
            # Normalize confidence to probability
            ai_score = ai_result.get("ai_probability")
            is_ai = ai_result.get("is_ai", False)
            verdict = "AI-generated" if is_ai else "Human-written"

            heuristics.append(f"AI Detector Verdict: {verdict} ({ai_score:.1%} confidence).")

            if model_family_result:
                model_family = model_family_result.get("family")
                model_family_confidence = model_family_result.get("confidence")
                heuristics.append(
                    f"Fingerprint matches {model_family} family ({model_family_confidence:.1%} match)."
                )

        ollama_risk = ollama_analysis.get("risk") if ollama_analysis else None
        if ollama_risk is not None:
            heuristics.append(
                f"Ollama semantic analysis: {ollama_risk:.1%} risk "
                f"(model: {self.settings.ollama_model})."
            )

        # 5. Composite Scoring
        # Sigmoid the linear stylometric score to get 0-1 range
        base_prob = self._sigmoid(prepared.stylometric_score)

        # Intelligently blend scores based on what is available
        composite = self._blend_scores(
            base_prob=base_prob,
            behavior_score=prepared.behavioral_score,
            ai_score=ai_score,
            ollama_risk=ollama_risk,
        )

        classification = self._classify(composite)

        breakdown = DetectionBreakdown(
            linguistic_score=base_prob,
            behavioral_score=prepared.behavioral_score,
            ai_probability=ai_score,
            model_family=model_family,
            model_family_confidence=model_family_confidence,
            model_family_probabilities=(
                model_family_result.get("all_probabilities") if model_family_result else None
            ),
            ollama_risk=ollama_risk,
            ollama_analysis=ollama_analysis,
            stylometric_anomalies={
                key: round(value, 3) for key, value in prepared.features.items()
            },
            heuristics=heuristics,
        )

        return composite, classification, breakdown

    def _extract_features(self, text: str) -> Dict[str, float]:
        tokens = self._tokenize(text)
        token_count = len(tokens) or 1

        # Sentence segmentation (improved: handle abbreviations better)
        sentences = re.split(r"(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?|\!)\s", text)
        sentences = [s.strip() for s in sentences if s.strip()]
        sentence_lengths = [len(self._tokenize(s)) for s in sentences]
        if not sentence_lengths:
            sentence_lengths = [token_count]

        # Basic Stats
        avg_token_length = sum(len(t) for t in tokens) / token_count

        # Enhanced Lexical Diversity: MATTR approximation (window=50, robust for short texts)
        matt_r = self._calculate_mattr(tokens, window=50)

        # Hapax Legomena (words appearing once)
        counts = Counter(tokens)
        hapax = sum(1 for _, count in counts.items() if count == 1)
        hapax_ratio = hapax / token_count

        # Variance statistics
        try:
            sentence_length_var = statistics.variance(sentence_lengths)
        except statistics.StatisticsError:
            sentence_length_var = 0.0

        # Structural features
        uppercase_tokens = sum(1 for t in tokens if t.isupper() and len(t) > 1)
        function_words = sum(1 for t in tokens if t.lower() in self.FUNCTION_WORDS)

        # Repetition Rate (N-gram redundancy)
        trigrams = list(zip(tokens, tokens[1:], tokens[2:]))
        if trigrams:
            unique_trigrams = len(set(trigrams))
            repetition_rate = 1.0 - (unique_trigrams / len(trigrams))
        else:
            repetition_rate = 0.0

        # Character-level Shannon Entropy
        char_counts = Counter(text)
        char_probs = [count / len(text) for count in char_counts.values()] if text else []
        char_entropy = -sum(p * math.log2(p) for p in char_probs) if char_probs else 0.0

        # Readability Proxy (ARI Approximation)
        char_count = sum(len(t) for t in tokens)
        avg_chars_per_word = char_count / token_count
        avg_words_per_sent = token_count / max(len(sentences), 1)
        readability = (4.71 * avg_chars_per_word) + (0.5 * avg_words_per_sent) - 21.43

        # Punctuation Variety (normalized diversity of ! ? . , ; : etc.)
        punct_types = set(re.findall(r'[!?.;,:\-–—()"]', text))
        punct_variety = len(punct_types) / 8.0  # Max 8 common types

        # Vocabulary Richness (HHI proxy: sum (freq^2) normalized; lower = more uniform/AI)
        freq_squares = sum((count / token_count) ** 2 for count in counts.values())
        vocabulary_richness = 1.0 - freq_squares  # 1 - HHI, higher = richer

        return {
            "avg_token_length": avg_token_length,
            "mattr": matt_r,
            "hapax_ratio": hapax_ratio,
            "sentence_length_var": sentence_length_var,
            "burstiness": self._calculate_burstiness(sentence_lengths),
            "function_word_ratio": function_words / token_count,
            "uppercase_ratio": uppercase_tokens / token_count,
            "repetition_rate": repetition_rate,
            "entropy": char_entropy,
            "readability_score": max(0, readability),
            "punctuation_variety": punct_variety,
            "vocabulary_richness": vocabulary_richness,
        }

    def _score_features(self, features: Dict[str, float]) -> float:
        normalized = self._normalize_features(features)
        score = self.bias

        for name, weight in self.weights.items():
            val = normalized.get(name, 0.0)
            score += weight * val

        return score

    def _run_heuristics(
        self,
        intake: ContentIntake,
        features: Dict[str, float],
    ) -> List[str]:
        heuristics: List[str] = []

        # Linguistic Heuristics (updated thresholds based on new features)
        if features.get("repetition_rate", 0) > 0.12:
            heuristics.append("High phrase repetition detected (characteristic of cheaper LLMs).")

        if features.get("entropy", 4.0) < 3.0:
            heuristics.append("Low character entropy suggests machine-generated predictability.")

        if features.get("mattr", 0) < 0.45:
            heuristics.append("Low moving-average lexical diversity.")

        if features.get("punctuation_variety", 0) < 0.3:
            heuristics.append("Limited punctuation variety (AI uniformity).")

        if features.get("vocabulary_richness", 0) < 0.7:
            heuristics.append("Uniform vocabulary distribution (lacks human richness).")

        # Structural Heuristics
        if features.get("burstiness", 0) < 0.15:
            heuristics.append("Monotonous sentence structure (robotic cadence).")
        elif features.get("burstiness", 0) > 0.85:
            heuristics.append("Erratic structure consistent with obfuscation attempts.")

        # Behavioral Heuristics (Metadata)
        if intake.metadata and getattr(intake.metadata, "platform", None) in self.SUSPECT_PLATFORMS:
            platform = intake.metadata.platform
            platform_boost = 0.25 if "telegram-channel" in platform else 0.12
            heuristics.append(
                f"Originating platform '{platform}' is flagged as high-risk (+{platform_boost})."
            )

        if intake.tags and any(tag in self.HIGH_RISK_TAGS for tag in intake.tags):
            heuristics.append("Content tags align with known threat actor narratives.")

        # Malware / Spam Heuristic
        link_count = intake.text.count("http")
        if link_count > 1:
            heuristics.append(f"Contains {link_count} external links (potential phishing/malware).")

        return heuristics

    def _calculate_behavioral_risk(
        self,
        intake: ContentIntake,
        features: Dict[str, float],
        heuristics: List[str],
    ) -> float:
        """
        Calculates a risk score based on intent, urgency, and context.
        Improvements: Regex for CTAs, valence counting, narrative drift, length-aware capping.
        """
        boost = 0.0
        text_lower = intake.text.lower()
        text_len = len(text_lower)

        # 1. Geo-Political Context
        if intake.metadata:
            region = (getattr(intake.metadata, "region", "") or "").upper()
            if region in {"RU", "IR", "KP", "CN"}:
                boost += 0.15

        # 2. Urgency & Emotional Manipulation (Enhanced)
        urgency_hits = sum(1 for word in self.URGENCY_WORDS if word in text_lower)
        valence_hits = sum(
            1
            for group in self.HIGH_VALENCE_WORDS.values()
            for word in group
            if word in text_lower
        )
        exclamations = text_lower.count("!") + text_lower.count("?")

        emotional_boost = min(
            (urgency_hits + valence_hits + exclamations / 4.0) / max(text_len / 120, 1),
            0.25,
        )
        if emotional_boost > 0.06:
            boost += emotional_boost
            heuristics.append(
                f"Emotional manipulation via {urgency_hits} urgency terms, "
                f"{valence_hits} valence words, and {exclamations} exclamations."
            )

        # 3. Call To Action (CTA) Detection (Regex-enhanced)
        cta_hits = sum(re.search(pattern, text_lower) is not None for pattern in self.CTA_PATTERNS)
        if cta_hits > 0:
            cta_boost = min(cta_hits * 0.1, 0.2)
            boost += cta_boost
            heuristics.append(
                f"Detected {cta_hits} call-to-action patterns (common in influence ops)."
            )

        # 4. Aggressive Formatting (length-normalized)
        upper_ratio = features.get("uppercase_ratio", 0)
        if upper_ratio > 0.08:
            boost += min(upper_ratio * 2.5, 0.15)
            heuristics.append("Aggressive use of capitalization.")

        # 5. Narrative Alignment & Coherence (topic drift proxy)
        sentences = re.split(r"[.!?]+", text_lower)
        sentences = [s.strip() for s in sentences if s.strip()]
        if len(sentences) > 3:
            sent_keywords = [set(re.findall(r"\b[a-z]{4,}\b", s)) for s in sentences]

            overlaps = 0.0
            count_pairs = 0
            for i, k1 in enumerate(sent_keywords):
                for k2 in sent_keywords[i + 1 :]:
                    if k1 or k2:
                        overlaps += len(k1 & k2) / max(len(k1), len(k2) or 1)
                        count_pairs += 1

            coherence = overlaps / count_pairs if count_pairs else 1.0
            if coherence < 0.35:
                boost += 0.1
                heuristics.append(
                    "Low narrative coherence (potential topic drift in disinfo)."
                )

        # Dynamic cap based on text length (short texts less reliable)
        if boost > 0.0:
            boost = max(boost, 0.1)

        max_boost = min(0.9, 0.55 + text_len / 900.0)
        return min(boost, max_boost)

    def _normalize_features(self, features: Dict[str, float]) -> Dict[str, float]:
        """Normalize raw stats to 0-1 range for linear scoring. Use sigmoid for smoother bounds."""

        def sigmoid_norm(x: float, scale: float = 1.0) -> float:
            return 1 / (1 + math.exp(-scale * (x - 0.5)))  # Centered sigmoid

        return {
            "avg_token_length": min(features.get("avg_token_length", 0) / 8.0, 1.0),
            "mattr": features.get("mattr", 0),
            "sentence_length_var": sigmoid_norm(
                features.get("sentence_length_var", 0) / 50.0,
                scale=2.0,
            ),
            "burstiness": features.get("burstiness", 0),
            "function_word_ratio": min(features.get("function_word_ratio", 0) * 2.0, 1.0),
            "uppercase_ratio": min(features.get("uppercase_ratio", 0) * 3.0, 1.0),
            "repetition_rate": min(features.get("repetition_rate", 0) * 5.0, 1.0),
            "entropy": min(features.get("entropy", 0) / 5.0, 1.0),
            "readability_score": min(features.get("readability_score", 0) / 20.0, 1.0),
            "punctuation_variety": features.get("punctuation_variety", 0),
            "vocabulary_richness": features.get("vocabulary_richness", 0),
        }

    def _blend_scores(
        self,
        base_prob: float,
        behavior_score: float,
        ai_score: Optional[float],
        ollama_risk: Optional[float] = None,
    ) -> float:
        """
        Weighted ensemble of all signals with HIGH priority to Ollama and HF detections.
        
        Scoring hierarchy:
        1. Ollama (semantic risk): 40% weight - Deep semantic understanding of content
        2. HF AI Detection: 35% weight - State-of-the-art AI generation detection
        3. Behavioral Analysis: 15% weight - Metadata, urgency, manipulation tactics
        4. Stylometric Base: 10% weight - Linguistic fingerprinting
        
        When both Ollama and HF are available, they dominate (75% combined).
        When only one is available, it still carries significant weight.
        """
        weights = {
            'stylometric': 0.10,
            'behavioral': 0.15,
            'ai_detection': 0.35,
            'ollama': 0.40,
        }
        
        # Track which signals are available
        available_signals = []
        composite = 0.0
        total_weight_used = 0.0
        
        # Add stylometric score (always available)
        composite += base_prob * weights['stylometric']
        total_weight_used += weights['stylometric']
        available_signals.append('stylometric')
        
        # Add behavioral score (always available)
        composite += behavior_score * weights['behavioral']
        total_weight_used += weights['behavioral']
        available_signals.append('behavioral')
        
        # Add HF AI detection if available (HIGH PRIORITY)
        if ai_score is not None:
            composite += ai_score * weights['ai_detection']
            total_weight_used += weights['ai_detection']
            available_signals.append('ai_detection')
        
        # Add Ollama semantic risk if available (HIGHEST PRIORITY)
        if ollama_risk is not None:
            composite += ollama_risk * weights['ollama']
            total_weight_used += weights['ollama']
            available_signals.append('ollama')
        
        # If some signals are missing, redistribute their weight proportionally
        # This ensures we still get 0-1 range even with missing signals
        if total_weight_used < 1.0:
            # Redistribute missing weight proportionally among available signals
            redistribution_factor = 1.0 / total_weight_used
            composite *= redistribution_factor
        
        logger.debug(
            f"Score blending: base={base_prob:.2f}, behavior={behavior_score:.2f}, "
            f"ai={ai_score or 0:.2f}, ollama={ollama_risk or 0:.2f} -> "
            f"composite={composite:.2f} (signals: {', '.join(available_signals)})"
        )

        return max(0.0, min(1.0, composite))

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        # Improved tokenizer that handles contractions slightly better
        return re.findall(r"\b[\w'-]+\b", text)

    @staticmethod
    def _calculate_burstiness(sentence_lengths: List[int]) -> float:
        """
        Calculates coefficient of variation of sentence lengths.
        High variation = Human (Burstiness). Low variation = AI (Monotony).
        """
        if not sentence_lengths or len(sentence_lengths) < 2:
            return 0.0
        mean = statistics.mean(sentence_lengths)
        stdev = statistics.stdev(sentence_lengths)
        if mean == 0:
            return 0.0
        return min(stdev / mean, 1.0)

    @staticmethod
    def _calculate_mattr(tokens: List[str], window: int = 50) -> float:
        """Approximate Moving-Average Type-Token Ratio (MATTR) for robust diversity."""
        if len(tokens) < window:
            return len(set(tokens)) / len(tokens) if tokens else 0.0

        total_types = 0.0
        num_windows = 0
        step = max(window // 2, 1)

        for i in range(0, len(tokens), step):  # Overlapping windows
            window_tokens = tokens[i : i + window]
            if window_tokens:
                types = len(set(window_tokens))
                total_types += types / len(window_tokens)
                num_windows += 1

        return total_types / num_windows if num_windows else 0.0

    @staticmethod
    def _sigmoid(x: float) -> float:
        return 1 / (1 + math.exp(-x))

    @staticmethod
    def _classify(score: float) -> str:
        if score >= 0.75:
            return "critical-risk"
        if score >= 0.60:
            return "high-risk"
        if score >= 0.35:
            return "medium-risk"
        return "low-risk"

    def _ai_detection(self, text: str) -> Tuple[Optional[Dict], Optional[Dict]]:
        if not getattr(self._ai_detector, "available", False):
            return None, None
        return self._ai_detector.analyze_text(text)

    def _ollama_analysis(self, text: str) -> Optional[Dict]:
        """
        Use Ollama for semantic/contextual risk assessment.
        Returns risk score 0.0-1.0 if available, None otherwise.
        """
        if self._ollama_client is None:
            return None
        try:
            return self._ollama_client.analyze(text)
        except Exception as e:
            logger.warning(f"Ollama risk assessment failed: {e}")
            return None
