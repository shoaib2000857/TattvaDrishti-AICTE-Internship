import { useEffect, useRef, useState } from "react";

const minCharacters = 20;
const reverseGeocoderUrl =
  process.env.NEXT_PUBLIC_REVERSE_GEOCODER_URL ||
  "https://nominatim.openstreetmap.org/reverse";

const CITIES = [
  "Agartala", "Aizawl", "Ajmer", "Akola", "Aligarh", "Prayagraj (Allahabad) ", "Alwar", "Ambala", "Amravati", "Amritsar",
  "Anantapur", "Ankleshwar", "Aurangabad", "Avadi", "Abu Dhabi", "Accra", "Addis Ababa", "Adelaide", "Agra", "Ahmedabad",
  "Algiers", "Amman", "Amsterdam", "Ankara", "Antananarivo", "Asunción", "Athens", "Atlanta", "Auckland", "Austin",
  "Bahadurgarh", "Ballari (Bellary)", "Bareilly", "Bathinda", "Belagavi (Belgaum)", "Bharatpur", "Bharuch", "Bhavnagar",
  "Bhilai", "Bhilwara", "Bhiwandi", "Bhiwani", "Bhubaneswar", "Bhuj", "Bidar", "Bilaspur", "Bokaro Steel City", "Bulandshahr",
  "Baghdad", "Baku", "Baltimore", "Bamako", "Bandung", "Bangalore (Bengaluru)", "Bangkok", "Barcelona", "Basel", "Baton Rouge",
  "Beijing", "Beirut", "Belgrade", "Belo Horizonte", "Benghazi", "Berlin", "Bern", "Bhopal", "Birmingham", "Bogotá",
  "Boston", "Brasília", "Bratislava", "Brazzaville", "Brisbane", "Brussels", "Bucharest", "Budapest", "Buenos Aires",
  "Chandrapur", "Chapra", "Coimbatore", "Cuttack", "Cairo", "Calgary", "Canberra", "Cape Town", "Caracas", "Casablanca",
  "Cebu", "Chandigarh", "Changsha", "Chennai", "Chicago", "Chittagong", "Chongqing", "Colombo", "Columbus", "Copenhagen", "Cordoba",
  "Davanagere", "Dehradun", "Dewas", "Dhanbad", "Dharamsala", "Dibrugarh", "Durg", "Dallas", "Dakar", "Dalian",
  "Dar es Salaam", "Delhi", "Denver", "Detroit", "Dhaka", "Doha", "Dongguan", "Douala", "Dubai", "Dublin", "Durban",
  "Edinburgh", "Edmonton", "Ekurhuleni", "Faridabad", "Farrukhabad", "Firozabad", "Faisalabad", "Florence", "Fort Worth",
  "Frankfurt", "Fukuoka", "Gandhinagar", "Gaya", "Ghaziabad", "Gorakhpur", "Gulbarga (Kalaburagi)", "Guntur", "Gurugram",
  "Gaborone", "Gdansk", "Geneva", "Genoa", "Glasgow", "Goa", "Guadalajara", "Guangzhou", "Guatemala City", "Gujranwala",
  "Haifa", "Hamburg", "Hangzhou", "Hanoi", "Harare", "Havana", "Helsinki", "Ho Chi Minh City", "Hong Kong", "Houston",
  "Hyderabad (India)", "Ibadan", "Incheon", "Indore", "Istanbul", "Izmir", "Jabalpur", "Jalandhar", "Jalgaon", "Jammu",
  "Jamnagar", "Jamshedpur", "Jhansi", "Jodhpur", "Junagadh", "Jakarta", "Jeddah", "Johannesburg", "Kabul", "Kampala",
  "Kanpur", "Karachi", "Kathmandu", "Kazan", "Kigali", "Kingston", "Kinshasa", "Kobe", "Kolkata", "Kuala Lumpur",
  "Kunming", "Kuwait City", "Kyiv", "Kyoto", "Lagos", "Lahore", "Lanzhou", "Las Vegas", "Leeds", "Lima", "Lisbon",
  "London", "Los Angeles", "Louisville", "Luanda", "Lucknow", "Lusaka", "Lyon", "Madrid", "Mahé", "Makassar",
  "Managua", "Manama", "Manaus", "Manila", "Maputo", "Marrakesh", "Marseille", "Mashhad", "Mazatlán", "Medan",
  "Medellín", "Melbourne", "Memphis", "Mexico City", "Miami", "Milan", "Milwaukee", "Minsk", "Mississauga", "Mogadishu",
  "Monrovia", "Monterrey", "Montevideo", "Montreal", "Moscow", "Mumbai", "Munich", "Nairobi", "Nagoya", "Nagpur",
  "Nanjing", "Nanning", "Nagercoil", "Nanded", "Nashik", "Nellore", "Noida", "North Lakhimpur", "Naples", "Nashville",
  "New Delhi", "New Orleans", "New York", "Newark", "Nice", "Ningbo", "Nizhny Novgorod", "Nouakchott", "Novosibirsk",
  "Oklahoma City", "Omaha", "Osaka", "Oslo", "Ottawa", "Panama City", "Paris", "Patna", "Perth", "Philadelphia",
  "Phnom Penh", "Phoenix", "Pittsburgh", "Port Elizabeth", "Port Harcourt", "Port Louis", "Port Moresby", "Portland",
  "Porto", "Prague", "Pretoria", "Pune", "Qingdao", "Quebec City", "Quito", "Raebareli", "Raichur", "Raipur",
  "Rajahmundry", "Rajkot", "Ranchi", "Ratlam", "Rewa", "Rohtak", "Rourkela", "Rabat", "Raleigh", "Recife",
  "Reykjavik", "Richmond", "Rio de Janeiro", "Riyadh", "Rome", "Rosario", "Rotterdam", "Sacramento", "Saint Petersburg",
  "Salt Lake City", "San Antonio", "San Diego", "San Francisco", "San José (Costa Rica)", "San Jose (USA)", "San Juan",
  "San Salvador", "Sana'a", "Santiago", "Santo Domingo", "São Paulo", "Seattle", "Sendai", "Seoul", "Seville",
  "Shanghai", "Sharjah", "Shenzhen", "Shijiazhuang", "Singapore", "Skopje", "Sofia", "St. Louis", "Stockholm", "Stuttgart",
  "Surat", "Suva", "Sydney", "Taipei", "Tallinn", "Tangier", "Tampa", "Tashkent", "Tbilisi", "Tehran", "Tel Aviv",
  "Tianjin", "Tijuana", "Tilburg", "Tokyo", "Toronto", "Tripoli", "Tunis", "Ulaanbaatar", "Valencia", "Vancouver",
  "Varanasi", "Venice", "Vienna", "Vientiane", "Vilnius", "Virginia Beach", "Warsaw", "Washington D.C.", "Wellington",
  "Wenzhou", "Winnipeg", "Wuhan", "Wuxi", "Warangal", "Xiamen", "Xi'an", "Yaoundé", "Yerevan", "Yokohama", "Yamunanagar",
  "Zirakpur", "Zagreb", "Zaragoza", "Zhengzhou", "Zibo", "Zurich"
];

export default function IntakeForm({
  onSubmit,
  isSubmitting,
  onValidationError,
  variant = "dark",
  metadataLabelStyle = "normal",
}) {
  const [text, setText] = useState("");
  const [language, setLanguage] = useState("en");
  const [source, setSource] = useState("");
  const [platform, setPlatform] = useState("");
  const [region, setRegion] = useState("");
  const [actorId, setActorId] = useState("");
  const [tags, setTags] = useState("");
  const [showRegionSuggestions, setShowRegionSuggestions] = useState(false);
  const [filteredCities, setFilteredCities] = useState([]);
  const recognitionRef = useRef(null);
  const regionInputRef = useRef(null);
  const [isListening, setIsListening] = useState(false);
  const [speechSupported, setSpeechSupported] = useState(true);
  const [speechError, setSpeechError] = useState("");
  const [isLocating, setIsLocating] = useState(false);
  const [locationError, setLocationError] = useState("");
  const [detectedCoordinates, setDetectedCoordinates] = useState(null);
  const [showPreview, setShowPreview] = useState(false);

  const isSimple = variant === "simple";
  const isLight = variant === "light" || isSimple;
  const inputClass = isLight
    ? "w-full rounded-xl border border-slate-200 bg-white px-3.5 py-3 text-sm text-slate-800 shadow-sm placeholder:text-slate-400 focus:border-blue-500 focus:outline-none focus:ring-4 focus:ring-blue-100"
    : "input";
  const textareaClass = isLight
    ? "mt-2 w-full resize-y rounded-2xl border border-slate-200 bg-white px-4 py-4 text-base leading-7 text-slate-900 shadow-sm placeholder:text-slate-400 focus:border-blue-500 focus:outline-none focus:ring-4 focus:ring-blue-100"
    : "mt-2 w-full rounded-2xl border border-white/10 bg-slate-950/70 px-4 py-3 text-sm text-slate-100 placeholder:text-slate-500 focus:border-emerald-400 focus:outline-none focus:ring-2 focus:ring-emerald-500/50";
  const containerClass = isSimple
    ? "space-y-6"
    : isLight
    ? "mt-6 space-y-6 rounded-[28px] border border-slate-200 bg-white p-6 shadow-xl shadow-slate-200/70"
    : "mt-6 space-y-6 rounded-3xl border border-white/10 bg-slate-900/70 p-6 shadow-2xl shadow-black/30";
  const titleClass = isLight
    ? "text-2xl font-semibold text-slate-900"
    : "text-2xl font-semibold text-white";
  const subtitleClass = isLight
    ? "text-sm text-slate-600"
    : "text-sm text-slate-400";
  const labelClass = isLight
    ? "text-sm font-semibold text-slate-700"
    : "text-sm font-semibold text-slate-200";
  const voiceButtonActiveClass = isLight
    ? "border-rose-200 bg-rose-50 text-rose-700"
    : "border-rose-300/70 bg-rose-500/10 text-rose-200";
  const voiceButtonIdleClass = isLight
    ? "border-emerald-200 bg-emerald-50 text-emerald-700"
    : "border-emerald-400/40 bg-emerald-500/10 text-emerald-200";
  const statusTextClass = isLight ? "text-xs text-slate-500" : "text-xs text-slate-400";
  const metadataLabelEmphasis = metadataLabelStyle === "bold" ? "bold" : "normal";

  useEffect(() => {
    if (typeof window === "undefined") return;
    const SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setSpeechSupported(false);
      recognitionRef.current = null;
      return;
    }
    const recognition = new SpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = language?.trim() || "en";
    recognition.onresult = (event) => {
      let transcriptChunk = "";
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const result = event.results[i];
        if (result.isFinal && result[0]?.transcript) {
          transcriptChunk += result[0].transcript;
        }
      }
      if (transcriptChunk) {
        const cleaned = transcriptChunk.replace(/\s+/g, " ").trim();
        setText((previous) => {
          const prefix = previous && !previous.endsWith(" ") ? `${previous} ` : previous || "";
          return `${prefix || ""}${cleaned}`.trim();
        });
      }
    };
    recognition.onerror = (event) => {
      setIsListening(false);
      setSpeechError(
        event.error === "not-allowed"
          ? "Microphone permission denied. Please allow access to dictate."
          : "Speech capture interrupted. Please try again."
      );
    };
    recognition.onend = () => {
      setIsListening(false);
    };
    recognitionRef.current = recognition;
    setSpeechSupported(true);

    return () => {
      recognition.onresult = null;
      recognition.onerror = null;
      recognition.onend = null;
      recognition.stop();
      recognitionRef.current = null;
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (recognitionRef.current) {
      recognitionRef.current.lang = language?.trim() || "en";
    }
  }, [language]);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (regionInputRef.current && !regionInputRef.current.contains(event.target)) {
        setShowRegionSuggestions(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleRegionChange = (value) => {
    setLocationError("");
    setDetectedCoordinates(null);
    setRegion(value);
    if (value.trim()) {
      const filtered = CITIES.filter(city =>
        city.toLowerCase().includes(value.toLowerCase())
      ).slice(0, 10); // Limit to 10 suggestions
      setFilteredCities(filtered);
      setShowRegionSuggestions(filtered.length > 0);
    } else {
      setFilteredCities([]);
      setShowRegionSuggestions(false);
    }
  };

  const selectCity = (city) => {
    setLocationError("");
    setDetectedCoordinates(null);
    setRegion(city);
    setShowRegionSuggestions(false);
    setFilteredCities([]);
  };

  const handleDetectLocation = () => {
    if (typeof navigator === "undefined" || !navigator.geolocation) {
      setLocationError("Location detection is unavailable in this browser.");
      return;
    }
    setIsLocating(true);
    setLocationError("");
    navigator.geolocation.getCurrentPosition(
      async ({ coords }) => {
        setDetectedCoordinates({
          latitude: coords.latitude,
          longitude: coords.longitude,
          accuracy_meters: Math.round(coords.accuracy),
        });
        const fallback = `${coords.latitude.toFixed(4)}, ${coords.longitude.toFixed(4)}`;
        try {
          const query = new URLSearchParams({
            format: "jsonv2",
            lat: String(coords.latitude),
            lon: String(coords.longitude),
            zoom: "10",
            addressdetails: "1",
          });
          const response = await fetch(
            `${reverseGeocoderUrl}?${query.toString()}`,
            { headers: { "Accept-Language": navigator.language || "en" } }
          );
          if (!response.ok) throw new Error("Reverse lookup failed");
          const result = await response.json();
          const address = result.address || {};
          const detectedRegion =
            address.city ||
            address.town ||
            address.village ||
            address.municipality ||
            address.county ||
            address.state_district ||
            address.state;
          setRegion(detectedRegion || fallback);
          setShowRegionSuggestions(false);
          setFilteredCities([]);
          if (!detectedRegion) {
            setLocationError("City lookup was unavailable; coordinates were used.");
          }
        } catch {
          setRegion(fallback);
          setShowRegionSuggestions(false);
          setFilteredCities([]);
          setLocationError("City lookup was unavailable; coordinates were used.");
        } finally {
          setIsLocating(false);
        }
      },
      (error) => {
        setIsLocating(false);
        if (error.code === error.PERMISSION_DENIED) {
          setLocationError("Location permission was denied. Enter a region manually.");
        } else if (error.code === error.TIMEOUT) {
          setLocationError("Location request timed out. Please try again.");
        } else {
          setLocationError("Your location could not be detected.");
        }
      },
      { enableHighAccuracy: false, timeout: 10000, maximumAge: 300000 }
    );
  };

  const stopDictation = () => {
    if (recognitionRef.current && isListening) {
      recognitionRef.current.stop();
    }
  };

  const handleToggleDictation = () => {
    if (!recognitionRef.current) {
      setSpeechError("Speech capture is unavailable in this browser.");
      return;
    }
    if (isListening) {
      stopDictation();
      return;
    }
    setSpeechError("");
    try {
      recognitionRef.current.lang = language?.trim() || "en";
      recognitionRef.current.start();
      setIsListening(true);
    } catch (error) {
      setSpeechError("Unable to access the microphone. Please try again.");
    }
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!text || text.trim().length < minCharacters) {
      onValidationError?.(
        `Narrative must contain at least ${minCharacters} characters.`
      );
      return;
    }
    if (!region || !region.trim()) {
      onValidationError?.("Region (city/district) is required.");
      return;
    }
    const payload = {
      text: text.trim(),
      language: language.trim() || "en",
      source: source.trim() || "unknown",
      tags: tags
        .split(",")
        .map((tag) => tag.trim())
        .filter(Boolean),
      metadata: {
        platform: platform.trim() || "unspecified",
        region: region.trim(),
        actor_id: actorId.trim() || null,
        attributes: detectedCoordinates
          ? { detected_location: detectedCoordinates }
          : {},
      },
    };
    const success = await onSubmit(payload);
    if (success) {
      stopDictation();
      setText("");
      setLanguage("en");
      setSource("");
      setPlatform("");
      setRegion("");
      setActorId("");
      setTags("");
      setSpeechError("");
      setDetectedCoordinates(null);
    }
  };

  return (
    <form onSubmit={handleSubmit} className={containerClass}>
      <header className={`flex flex-col gap-2 ${isSimple ? "sr-only" : ""}`}>
        <h2 className={titleClass}>
          Submit narrative for detection
        </h2>
        <p className={subtitleClass}>
          Paste flagged content, enrich with context, and trigger the end-to-end
          pipeline.
        </p>
      </header>
      <div>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <label htmlFor="payload-text" className={labelClass}>
          {isSimple ? "Message or narrative" : "Narrative payload"}
          </label>
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => setShowPreview((current) => !current)}
              className="rounded-full border border-cyan-500/40 bg-cyan-500/10 px-4 py-1.5 text-xs font-semibold text-cyan-200 transition hover:bg-cyan-500/20"
            >
              {showPreview ? "Hide preview" : "Preview"}
            </button>
            <button
              type="button"
              onClick={handleToggleDictation}
              disabled={!speechSupported || isSubmitting}
              className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-semibold tracking-wide transition focus:outline-none focus:ring-2 focus:ring-emerald-500/40 disabled:cursor-not-allowed disabled:opacity-40 ${
                isListening ? voiceButtonActiveClass : voiceButtonIdleClass
              }`}
            >
              <span
                className={`h-2 w-2 rounded-full ${
                  isListening ? "bg-rose-300 animate-pulse" : "bg-emerald-300"
                }`}
              />
              {isListening ? "Stop listening" : "Dictate"}
            </button>
          </div>
        </div>
        <textarea
          id="payload-text"
          name="text"
          rows={isSimple ? 8 : 6}
          required
          placeholder={
            isSimple
              ? "Paste the message, social media post, transcript, or suspicious text here…"
              : "Paste suspect content or hostile call-to-action..."
          }
          value={text}
          onChange={(event) => setText(event.target.value)}
          className={textareaClass}
        />
        {showPreview && (
          <NarrativePreview
            text={text}
            onClose={() => setShowPreview(false)}
          />
        )}
        <p className="mt-2 flex items-center justify-between gap-4 text-xs text-slate-500">
          <span>
            {isSimple
              ? "Use the original wording for a more reliable result."
              : `Minimum ${minCharacters} characters. The orchestrator runs heuristics, watermark checks, and graph ingestion automatically.`}
          </span>
          <span className={`shrink-0 font-medium ${text.trim().length >= minCharacters ? "text-emerald-700" : "text-slate-400"}`}>
            {text.trim().length} / {minCharacters} min
          </span>
        </p>
        {speechError && (
          <p className="mt-2 text-xs text-rose-300">{speechError}</p>
        )}
        {!speechSupported && !speechError && (
          <p className="mt-2 text-xs text-slate-500">
            Voice dictation is unavailable in this browser.
          </p>
        )}
      </div>

      <div className={`grid grid-cols-1 gap-4 text-sm ${isSimple ? "sm:grid-cols-2" : "md:grid-cols-3"}`}>
        <InputField label="Language" variant={variant} emphasis={metadataLabelEmphasis}>
          {isSimple ? (
            <select
              id="payload-language"
              value={language}
              onChange={(event) => setLanguage(event.target.value)}
              className={inputClass}
            >
              <option value="en">English</option>
              <option value="hi">Hindi</option>
              <option value="ur">Urdu</option>
              <option value="bn">Bengali</option>
              <option value="te">Telugu</option>
              <option value="ta">Tamil</option>
              <option value="mr">Marathi</option>
              <option value="gu">Gujarati</option>
              <option value="pa">Punjabi</option>
              <option value="kn">Kannada</option>
              <option value="ml">Malayalam</option>
            </select>
          ) : (
            <input
              id="payload-language"
              value={language}
              onChange={(event) => setLanguage(event.target.value)}
              className={inputClass}
            />
          )}
        </InputField>
        {isSimple && (
          <InputField label="Location / region" variant={variant} emphasis={metadataLabelEmphasis}>
            <RegionInput
              regionInputRef={regionInputRef}
              region={region}
              filteredCities={filteredCities}
              showRegionSuggestions={showRegionSuggestions}
              setShowRegionSuggestions={setShowRegionSuggestions}
              handleRegionChange={handleRegionChange}
              selectCity={selectCity}
              inputClass={inputClass}
              isLight={isLight}
              isLocating={isLocating}
              locationError={locationError}
              onDetectLocation={handleDetectLocation}
            />
          </InputField>
        )}
        {!isSimple && (
          <>
        <InputField label="Source channel" variant={variant} emphasis={metadataLabelEmphasis}>
          <input
            id="payload-source"
            value={source}
            placeholder="e.g. darknet, social-feed"
            onChange={(event) => setSource(event.target.value)}
            className={inputClass}
          />
        </InputField>
        <InputField label="Analyst tags" variant={variant} emphasis={metadataLabelEmphasis}>
          <input
            id="payload-tags"
            value={tags}
            placeholder="disinfo, amplification"
            onChange={(event) => setTags(event.target.value)}
            className={inputClass}
          />
        </InputField>
          </>
        )}
      </div>

      {isSimple ? (
        <details className="group rounded-2xl border border-slate-200 bg-slate-50/80">
          <summary className="flex cursor-pointer list-none items-center justify-between gap-4 px-4 py-3 text-sm font-semibold text-slate-700 marker:content-none">
            <span>
              Add more context <span className="font-normal text-slate-500">(optional)</span>
            </span>
            <svg className="h-4 w-4 text-slate-400 transition group-open:rotate-180" viewBox="0 0 20 20" fill="none" aria-hidden="true">
              <path d="m5 7.5 5 5 5-5" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </summary>
          <div className="grid grid-cols-1 gap-4 border-t border-slate-200 px-4 py-4 sm:grid-cols-2">
            <InputField label="Source channel" variant={variant} emphasis={metadataLabelEmphasis}>
              <input id="payload-source" value={source} placeholder="e.g. public tip, social feed" onChange={(event) => setSource(event.target.value)} className={inputClass} />
            </InputField>
            <InputField label="Platform" variant={variant} emphasis={metadataLabelEmphasis}>
              <input id="payload-platform" value={platform} placeholder="e.g. WhatsApp, Telegram" onChange={(event) => setPlatform(event.target.value)} className={inputClass} />
            </InputField>
            <InputField label="Reference / actor ID" variant={variant} emphasis={metadataLabelEmphasis}>
              <input id="payload-actor" value={actorId} placeholder="If one is available" onChange={(event) => setActorId(event.target.value)} className={inputClass} />
            </InputField>
            <InputField label="Tags" variant={variant} emphasis={metadataLabelEmphasis}>
              <input id="payload-tags" value={tags} placeholder="e.g. disinformation, threat" onChange={(event) => setTags(event.target.value)} className={inputClass} />
            </InputField>
          </div>
        </details>
      ) : (
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3 text-sm">
        <InputField label="Platform" variant={variant} emphasis={metadataLabelEmphasis}>
          <input
            id="payload-platform"
            value={platform}
            placeholder="telegram, state-media"
            onChange={(event) => setPlatform(event.target.value)}
            className={inputClass}
          />
        </InputField>
        <InputField label="Region" variant={variant} emphasis={metadataLabelEmphasis}>
          <RegionInput
            regionInputRef={regionInputRef}
            region={region}
            filteredCities={filteredCities}
            showRegionSuggestions={showRegionSuggestions}
            setShowRegionSuggestions={setShowRegionSuggestions}
            handleRegionChange={handleRegionChange}
            selectCity={selectCity}
            inputClass={inputClass}
            isLight={isLight}
            isLocating={isLocating}
            locationError={locationError}
            onDetectLocation={handleDetectLocation}
          />
        </InputField>
        <InputField label="Actor ID" variant={variant} emphasis={metadataLabelEmphasis}>
          <input
            id="payload-actor"
            value={actorId}
            placeholder="Suspected cell"
            onChange={(event) => setActorId(event.target.value)}
            className={inputClass}
          />
        </InputField>
      </div>
      )}

      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className={`flex items-center gap-2 ${statusTextClass}`}>
          <span className="h-2.5 w-2.5 rounded-full bg-emerald-400 animate-pulse" />
          {isSimple ? "Secure analysis service ready" : "Pipeline orchestration online"}
        </div>
        <button
          type="submit"
          disabled={isSubmitting}
          className={isSimple
            ? "inline-flex min-h-12 items-center justify-center gap-2 rounded-xl bg-blue-700 px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-blue-900/10 transition hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-200 disabled:cursor-not-allowed disabled:opacity-50"
            : "inline-flex items-center gap-2 rounded-full bg-emerald-400/90 px-6 py-2 text-sm font-semibold text-slate-950 transition hover:bg-emerald-300 focus:outline-none focus:ring-2 focus:ring-emerald-500/50 disabled:cursor-not-allowed disabled:opacity-50"}
        >
          {isSubmitting ? "Analysing…" : isSimple ? "Analyse message" : "Analyse narrative"}
          <svg
            className="h-4 w-4"
            viewBox="0 0 20 20"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              d="M4.167 10h11.666M10 4.167 15.833 10 10 15.833"
              stroke="#0f172a"
              strokeWidth="1.6"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>
      </div>
    </form>
  );
}

function NarrativePreview({ text, onClose }) {
  const preview = buildNarrativePreview(text);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4 py-6 backdrop-blur-sm">
      <div className="flex max-h-[88vh] w-full max-w-3xl flex-col overflow-hidden rounded-3xl border border-white/10 bg-slate-950 shadow-2xl shadow-black/60">
        <div className="flex items-start justify-between gap-4 border-b border-white/10 px-6 py-5">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.3em] text-cyan-300">
              Smart preview
            </p>
            <h3 className="mt-2 text-lg font-semibold text-white">
              Narrative readability check
            </h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs font-semibold text-slate-300 transition hover:bg-white/10"
          >
            Close
          </button>
        </div>
        <div className="overflow-y-auto px-6 py-5">
          {!preview.hasEnoughContent ? (
            <p className="rounded-2xl border border-white/10 bg-slate-900/70 px-5 py-4 text-xs leading-relaxed text-slate-500">
              Not enough content to preview.
            </p>
          ) : (
            <div className="rounded-2xl border border-white/10 bg-slate-950/80 px-5 py-4 text-sm leading-relaxed text-slate-200 whitespace-pre-wrap">
              <div className="mb-3 flex flex-wrap gap-4 border-b border-white/10 pb-3 text-[11px] text-slate-500">
                <span>{preview.wordCount} words</span>
                <span>{preview.sentenceCount} sentences</span>
                <span>{preview.readTime} min read</span>
              </div>
              <div dangerouslySetInnerHTML={{ __html: preview.html }} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function buildNarrativePreview(text) {
  const normalized = text.trim().replace(/\n{3,}/g, "\n\n");
  const wordCount = normalized ? normalized.split(/\s+/).filter(Boolean).length : 0;
  const sentenceMatches = normalized.match(/[^.!?]+[.!?]+|[^.!?]+$/g) || [];

  return {
    hasEnoughContent: normalized.length >= minCharacters,
    wordCount,
    sentenceCount: sentenceMatches.filter((sentence) => sentence.trim()).length,
    readTime: Math.max(1, Math.ceil(wordCount / 200)),
    html: highlightNarrativeSentences(normalized),
  };
}

function highlightNarrativeSentences(text) {
  const parts = text.match(/[^.!?]+[.!?]+[\])'"`’”]*\s*|[^.!?]+$/g) || [];
  return parts
    .map((part) => {
      const trailingWhitespace = part.match(/\s+$/)?.[0] || "";
      const sentence = trailingWhitespace ? part.slice(0, -trailingWhitespace.length) : part;
      const escapedSentence = escapeHtml(sentence);
      const escapedWhitespace = escapeHtml(trailingWhitespace);
      const hasAllCapsWord = /\b[A-Z]{2,}\b/.test(sentence);
      const hasExclamation = sentence.includes("!");

      if (hasAllCapsWord) {
        return `<span class="text-amber-300 font-semibold">${escapedSentence}</span>${escapedWhitespace}`;
      }
      if (hasExclamation) {
        return `<span class="text-rose-300">${escapedSentence}</span>${escapedWhitespace}`;
      }
      return `${escapedSentence}${escapedWhitespace}`;
    })
    .join("");
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function InputField({ label, children, variant = "dark", emphasis = "normal" }) {
  const isLight = variant === "light" || variant === "simple";
  const baseColor = isLight ? "text-slate-500" : "text-slate-400";
  const emphasisClass =
    emphasis === "bold"
      ? isLight
        ? "text-slate-900 font-semibold"
        : "text-white font-semibold"
      : baseColor;
  return (
    <label
      className={`flex flex-col gap-2 ${
        isLight ? "text-slate-700" : "text-slate-200"
      }`}
    >
      <span
        className={`text-xs uppercase tracking-[0.3em] ${emphasisClass}`}
      >
        {label}
      </span>
      {children}
    </label>
  );
}

function RegionInput({
  regionInputRef,
  region,
  filteredCities,
  showRegionSuggestions,
  setShowRegionSuggestions,
  handleRegionChange,
  selectCity,
  inputClass,
  isLight,
  isLocating,
  locationError,
  onDetectLocation,
}) {
  return (
    <div ref={regionInputRef} className="relative">
      <input
        id="payload-region"
        value={region}
        placeholder="Start typing a city or district"
        required
        onChange={(event) => handleRegionChange(event.target.value)}
        onFocus={() => {
          if (region.trim() && filteredCities.length > 0) {
            setShowRegionSuggestions(true);
          }
        }}
        className={inputClass}
        autoComplete="off"
      />
      <button
        type="button"
        onClick={onDetectLocation}
        disabled={isLocating}
        className={`mt-2 inline-flex w-full items-center justify-center gap-2 rounded-xl border px-3 py-2 text-xs font-semibold transition disabled:cursor-wait disabled:opacity-60 ${
          isLight
            ? "border-blue-200 bg-blue-50 text-blue-700 hover:bg-blue-100"
            : "border-cyan-400/30 bg-cyan-400/10 text-cyan-200 hover:bg-cyan-400/20"
        }`}
      >
        <svg className="h-4 w-4" viewBox="0 0 20 20" fill="none" aria-hidden="true">
          <circle cx="10" cy="10" r="3" stroke="currentColor" strokeWidth="1.5" />
          <path d="M10 2v2M10 16v2M2 10h2M16 10h2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
        {isLocating ? "Detecting location…" : "Use my location"}
      </button>
      {locationError ? (
        <p className={`mt-2 text-xs ${isLight ? "text-amber-700" : "text-amber-300"}`}>
          {locationError}
        </p>
      ) : null}
      {showRegionSuggestions && filteredCities.length > 0 && (
        <div className="absolute z-20 mt-1 max-h-60 w-full overflow-y-auto rounded-xl border border-slate-200 bg-white py-1 shadow-xl">
          {filteredCities.map((city) => (
            <button
              key={city}
              type="button"
              onClick={() => selectCity(city)}
              className="w-full px-4 py-2.5 text-left text-sm text-slate-700 transition-colors hover:bg-blue-50 hover:text-blue-800"
            >
              {city}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
