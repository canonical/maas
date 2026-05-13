# Copyright 2024-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from dataclasses import dataclass

from openai import OpenAI

from maasservicelayer.services.base import Service, ServiceCache

_PROMPT = """You are an expert translation engine for Canonical MAAS (Metal As A Service). Your sole purpose is to translate natural language requests into the exact MAAS machine query language.

RULES:
1. Respond ONLY with the raw query string. Do not include markdown formatting, backticks, or explanations.
2. The syntax for a filter is exactly `key:(=value)`.
3. For multiple values in the same key, use a comma and a new equals sign: `key:(=value1,=value2)`.
4. Separate multiple filters with a single space.
5. For IP addresses, always format them as CIDR subnets (e.g., 10.0.0.0/24).
6. Use `not_` keys to handle exclusions (e.g., `not_tags`, `not_subnets`, `not_arch`).
7. DO NOT guess, infer, or add any filters that the user did not explicitly mention. Translate strictly what is asked and nothing more.

VOCABULARY CONSTRAINTS:
- `status` must be one of: default, new, commissioning, failed_commissioning, missing, ready, reserved, deployed, retired, broken, deploying, allocated, failed_deployment, releasing, failed_releasing, disk_erasing, failed_disk_erasing, rescue_mode, entering_rescue_mode, failed_entering_rescue_mode, exiting_rescue_mode, failed_exiting_rescue_mode, testing, failed_testing.
- `deployment_target` must be either: memory, disk.
- Common keys include: arch, cpu_count, mem, tags, owner, pool, zone, subnets, mac_address, hostname.

EXAMPLES:
User: Find all generic amd64 servers that are ready.
Query: status:(=ready) arch:(=amd64/generic)

User: Show me nodes in commissioning or rescue mode owned by the admin.
Query: status:(=commissioning,=rescue_mode) owner:(=admin)

User: Give me virtual machines in the database pool that are not in the 10.10.0.0/24 subnet.
Query: tags:(=virtual) pool:(=database) not_subnets:(=10.10.0.0/24)

User: Find machines targeting RAM that have 8 cores.
Query: deployment_target:(=memory) cpu_count:(=8)

User: Exclude arm64 servers and find deployed machines in zone 2.
Query: not_arch:(=arm64/generic) status:(=deployed) zone:(=zone2)

User: Show me servers with 16 cores.
Query: cpu_count:(=16)
"""

_GRAMMAR = """# 1. The Entry Point
root ::= filter (" " filter)*

# 2. Branching Filters
filter ::= status_filter | deployment_target_filter | subnet_filter | generic_filter

# ==========================================
# STATUS SPECIFIC RULES
# ==========================================
status_filter ::= "status:(" status_value_list ")"
status_value_list ::= "=" status_value (",=" status_value)*
status_value ::= "default" | "new" | "commissioning" | "failed_commissioning" | "missing" | "ready" | "reserved" | "deployed" | "retired" | "broken" | "deploying" | "allocated" | "failed_deployment" | "releasing" | "failed_releasing" | "disk_erasing" | "failed_disk_erasing" | "rescue_mode" | "entering_rescue_mode" | "failed_entering_rescue_mode" | "exiting_rescue_mode" | "failed_exiting_rescue_mode" | "testing" | "failed_testing"

# ==========================================
# DEPLOYMENT TARGET SPECIFIC RULES
# ==========================================
deployment_target_filter ::= "deployment_target:(" deployment_target_value_list ")"
deployment_target_value_list ::= "=" deployment_target_value (",=" deployment_target_value)*
deployment_target_value ::= "memory" | "disk"

# ==========================================
# SUBNET SPECIFIC RULES (IPv4 & IPv6 CIDR)
# ==========================================
subnet_key ::= "subnets" | "not_subnets"
subnet_filter ::= subnet_key ":(" subnet_value_list ")"
subnet_value_list ::= "=" subnet_value (",=" subnet_value)*

# The LLM must output either a valid IPv4 shape or an IPv6 shape
subnet_value ::= ipv4_subnet | ipv6_subnet

# IPv4: Enforces up to 3 digits per octet, separated by dots, followed by a CIDR slash and digits
# We use [0-9] [0-9]? [0-9]? to ensure compatibility across all versions of llama.cpp
ipv4_subnet ::= [0-9] [0-9]? [0-9]? "." [0-9] [0-9]? [0-9]? "." [0-9] [0-9]? [0-9]? "." [0-9] [0-9]? [0-9]? "/" [0-9] [0-9]?

# IPv6: Enforces a mix of hex characters and colons, followed by a CIDR slash and digits
ipv6_subnet ::= [0-9a-fA-F:]+ "/" [0-9] [0-9]? [0-9]?

# ==========================================
# GENERIC RULES (For the remaining 46 keys)
# ==========================================
# 'status', 'deployment_target', 'subnets', and 'not_subnets' have been removed from this list
generic_keys ::= "agent_name" | "arch" | "cpu_count" | "cpu_speed" | "description" | "distro_series" | "domain" | "error_description" | "fabric_classes" | "fabrics" | "free_text" | "hostname" | "id" | "ip_addresses" | "link_speed" | "mac_address" | "mem" | "not_arch" | "not_cpu_count" | "not_cpu_speed" | "not_distro_series" | "not_fabric_classes" | "not_fabrics" | "not_id" | "not_in_pool" | "not_in_zone" | "not_ip_addresses" | "not_link_speed" | "not_mem" | "not_osystem" | "not_owner" | "not_pod" | "not_pod_type" | "not_tags" | "not_vlans" | "osystem" | "owner" | "parent" | "pod" | "pod_type" | "pool" | "spaces" | "tags" | "vlans" | "workloads" | "zone"

generic_filter ::= generic_keys ":(" generic_value_list ")"
generic_value_list ::= "=" generic_value (",=" generic_value)*
generic_value ::= [a-zA-Z0-9_./-]+
"""


@dataclass(slots=True)
class LLMSearchServiceCache(ServiceCache):
    openai_client: OpenAI | None = None


class LLMSearchService(Service):
    DEFAULT_CONFIG = {
        "base_url": "http://localhost:8336/v1",
        "api_key": "dummy-api-key",
        "model_name": "gemma",
        "temperature": 0.0,
        "max_tokens": 64,
    }

    @staticmethod
    def build_cache_object() -> ServiceCache:
        return LLMSearchServiceCache()

    @Service.from_cache_or_execute(attr="openai_client")
    def get_openai_client(self) -> OpenAI:
        return OpenAI(
            base_url=self.DEFAULT_CONFIG["base_url"],
            api_key="apikey",
            # default_headers={ # uncomment for Openrouter
            #     "X-OpenRouter-Cache": "true"
            # }
        )

    def translate(self, search_text: str) -> str:
        """Translate the search text into MAAS Machine query language."""
        client = self.get_openai_client()
        response = client.chat.completions.create(
            model=self.DEFAULT_CONFIG["model_name"],
            messages=[
                {"role": "system", "content": _PROMPT},
                {"role": "user", "content": search_text},
            ],
            temperature=self.DEFAULT_CONFIG["temperature"],
            max_tokens=self.DEFAULT_CONFIG["max_tokens"],
            extra_body={
                "cache_prompt": True,
                "grammar": _GRAMMAR,
            },
        )
        if content := response.choices[0].message.content:
            return content.strip()
        return ""
