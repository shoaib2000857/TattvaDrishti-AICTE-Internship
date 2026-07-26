import hashlib
import json
import random
from datetime import datetime
from typing import Dict, List, Literal
from uuid import uuid4

from ..config import get_settings
from ..schemas import SharingPackage, HopTrace


class SharingEngine:
    # Major hubs by destination country/region
    HOP_DESTINATIONS = {
        "USA": {
            "final": {"city": "Ashburn, US", "coords": [39.0438, -77.4874], "name": "Target SOC Collector", "provider": "US Gov Cloud"},
            "routes": [
                [{"city": "Mumbai, IN", "coords": [19.076, 72.8777], "name": "Analyst Edge Relay", "provider": "ISP Edge South Asia"},
                 {"city": "Dubai, AE", "coords": [25.2048, 55.2708], "name": "Middle East Transit Hub", "provider": "Subsea Gateway 5"},
                 {"city": "Frankfurt, DE", "coords": [50.1109, 8.6821], "name": "Frankfurt Threat Exchange", "provider": "DE-CIX Backbone"},
                 {"city": "London, UK", "coords": [51.5072, -0.1276], "name": "London Fusion Stack", "provider": "Atlantic Bridge 3"}],
            ]
        },
        "EU": {
            "final": {"city": "Brussels, BE", "coords": [50.8503, 4.3517], "name": "EU Cyber Command", "provider": "EU SecNet"},
            "routes": [
                [{"city": "Mumbai, IN", "coords": [19.076, 72.8777], "name": "Analyst Edge Relay", "provider": "ISP Edge South Asia"},
                 {"city": "Dubai, AE", "coords": [25.2048, 55.2708], "name": "Middle East Transit Hub", "provider": "Subsea Gateway 5"},
                 {"city": "Frankfurt, DE", "coords": [50.1109, 8.6821], "name": "Frankfurt Threat Exchange", "provider": "DE-CIX Backbone"}],
            ]
        },
        "IN": {
            "final": {"city": "New Delhi, IN", "coords": [28.6139, 77.2090], "name": "National Cyber Coordination", "provider": "NIC Core"},
            "routes": [
                [{"city": "Mumbai, IN", "coords": [19.076, 72.8777], "name": "Analyst Edge Relay", "provider": "ISP Edge South Asia"},
                 {"city": "Bengaluru, IN", "coords": [12.9716, 77.5946], "name": "Tech Hub Relay", "provider": "BSNL Backbone"}],
            ]
        },
        "AUS": {
            "final": {"city": "Canberra, AU", "coords": [-35.2809, 149.1300], "name": "AUS Defense Intel Hub", "provider": "ASD SecureNet"},
            "routes": [
                [{"city": "Mumbai, IN", "coords": [19.076, 72.8777], "name": "Analyst Edge Relay", "provider": "ISP Edge South Asia"},
                 {"city": "Singapore, SG", "coords": [1.3521, 103.8198], "name": "APAC Gateway", "provider": "SG-IX Hub"},
                 {"city": "Sydney, AU", "coords": [-33.8688, 151.2093], "name": "Sydney Relay", "provider": "Telstra Core"}],
            ]
        },
    }

    def __init__(self) -> None:
        self.settings = get_settings()

    def create_package(
        self,
        intake_id: str,
        destination: str,
        payload: Dict[str, str],
        policy_tags: List[str],
        risk_level: str = "low-risk",
        composite_score: float = 0.0,
        transfer_mode: Literal["encrypted", "blockchain"] = "encrypted",
    ) -> SharingPackage:
        package_id = f"pkg-{uuid4()}"
        created_at = datetime.utcnow()
        envelope = {
            "intake_id": intake_id,
            "destination": destination,
            "created_at": created_at.isoformat(),
            "payload": payload,
            "policy_tags": policy_tags,
        }
        signature = self._sign(envelope)
        hop_trace = self._generate_hop_trace(destination)
        return SharingPackage(
            package_id=package_id,
            created_at=created_at,
            destination=destination,
            policy_tags=policy_tags,
            payload={k: json.dumps(v) if isinstance(v, dict) else str(v) for k, v in payload.items()},
            signature=signature,
            hop_trace=hop_trace,
            risk_level=risk_level,
            composite_score=composite_score,
            transfer_mode=transfer_mode,
            transport_security=(
                "AES-256-GCM + TLS 1.3"
                if transfer_mode == "encrypted"
                else "Fernet-encrypted federated ledger demo"
            ),
        )

    def _generate_hop_trace(self, destination: str) -> List[HopTrace]:
        """Generate dynamic hop trace route based on destination."""
        dest_config = self.HOP_DESTINATIONS.get(destination)
        if not dest_config:
            # Fallback to USA route if destination not found
            dest_config = self.HOP_DESTINATIONS["USA"]
        
        # Pick a random route variant
        route_hops = random.choice(dest_config["routes"])
        final_hop = dest_config["final"]
        
        hops = []
        base_latency = 12
        
        # Build intermediate hops
        for idx, hop_data in enumerate(route_hops):
            latency = base_latency + idx * random.randint(8, 15) + random.randint(-4, 4)
            hops.append(HopTrace(
                id=f"HOP-{idx+1}-{hop_data['city'].replace(', ', '-').replace(' ', '-')}",
                name=hop_data["name"],
                city=hop_data["city"],
                coords=hop_data["coords"],
                ip=f"{random.randint(10, 192)}.{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}",
                provider=hop_data["provider"],
                latency=latency,
                note="Forwarding payload via encrypted tunnel."
            ))
        
        # Add final destination hop
        final_latency = base_latency + len(route_hops) * 15 + random.randint(-3, 5)
        hops.append(HopTrace(
            id=f"HOP-FINAL-{destination}",
            name=final_hop["name"],
            city=final_hop["city"],
            coords=final_hop["coords"],
            ip=f"{random.randint(10, 192)}.{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}",
            provider=final_hop["provider"],
            latency=final_latency,
            note="Payload delivered to receiving SOC."
        ))
        
        return hops

    def _sign(self, envelope: Dict[str, str]) -> str:
        serialised = json.dumps(envelope, sort_keys=True)
        digest = hashlib.sha256((self.settings.secret_key + serialised).encode("utf-8"))
        return digest.hexdigest()
