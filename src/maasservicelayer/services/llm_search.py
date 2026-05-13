# Copyright 2024-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from dataclasses import dataclass

from openai import OpenAI

from maasservicelayer.services.base import Service, ServiceCache

_PROMPT = """You are an expert translation engine for Canonical MAAS (Metal As A Service). Your sole purpose is to translate natural language requests into the exact MAAS machine query language.

CORE RULES:
1. Respond ONLY with the raw query string. No markdown, no backticks, no explanations.
2. Syntax Type A (Standard): For most keys (tags, owner, arch, status, etc.), use key:(=value). Multiple values: key:(=val1,val2).
3. Syntax Type B (Numeric/Capacity): For cpu_count, cpu_speed, mem, link_speed, physical_disk_count, total_storage (and their not_ versions), DO NOT use the "=" sign. Format as key:(value). Multiple values: key:(val1,val2).
4. UNIT CONVERSION: Values for 'mem' and 'total_storage' (and not_ versions) MUST be converted to MiB (Mebibyte) as raw integers.
   - Calculation: [GB] * 953.67 = MiB, rounded to the nearest integer.
   - DO NOT include the string "MiB" in the output.
5. Separate multiple filters with a single space.
6. Use CIDR notation for subnets (e.g., 10.1.1.0/24).
7. Use 'not_' keys for exclusions (e.g., not_tags, not_subnets).
8. DO NOT guess or add any filters not explicitly mentioned by the user.

VOCABULARY CONSTRAINTS:
- status: default, new, commissioning, failed_commissioning, missing, ready, reserved, deployed, retired, broken, deploying, allocated, failed_deployment, releasing, failed_releasing, disk_erasing, failed_disk_erasing, rescue_mode, entering_rescue_mode, failed_entering_rescue_mode, exiting_rescue_mode, failed_exiting_rescue_mode, testing, failed_testing.
- deployment_target: memory, disk.

EXAMPLES:
User: Find all generic amd64 servers that are ready.
Query: status:(=ready) arch:(=amd64/generic)

User: Show me servers with 16 cores and 32GB of RAM.
Query: cpu_count:(16) mem:(30518)

User: Find nodes with 2TB of storage that are not in rescue mode.
Query: total_storage:(1907349) not_status:(=rescue_mode)

User: Show me nodes in commissioning owned by admin or gr00t.
Query: status:(=commissioning) owner:(=admin,gr00t)

User: Find servers with 1Gbps link speed excluding the 10.0.0.0/24 subnet.
Query: link_speed:(1000) not_subnets:(=10.0.0.0/24)

User: Get machines with 4 cores, targeting disk, with 8GB or 16GB memory.
Query: cpu_count:(4) deployment_target:(=disk) mem:(7629,15259)
"""

_GRAMMAR = """# 1. The Entry Point
root ::= filter (" " filter)*

# 2. Branching Filters
filter ::= status_filter | deployment_target_filter | subnet_filter | numeric_filter | generic_filter

# ==========================================
# STATUS SPECIFIC RULES
# ==========================================
status_filter ::= "status:(" status_value_list ")"
status_value_list ::= "=" status_value ("," status_value)*
status_value ::= "default" | "new" | "commissioning" | "failed_commissioning" | "missing" | "ready" | "reserved" | "deployed" | "retired" | "broken" | "deploying" | "allocated" | "failed_deployment" | "releasing" | "failed_releasing" | "disk_erasing" | "failed_disk_erasing" | "rescue_mode" | "entering_rescue_mode" | "failed_entering_rescue_mode" | "exiting_rescue_mode" | "failed_exiting_rescue_mode" | "testing" | "failed_testing"

# ==========================================
# DEPLOYMENT TARGET SPECIFIC RULES
# ==========================================
deployment_target_filter ::= "deployment_target:(" deployment_target_value_list ")"
deployment_target_value_list ::= "=" deployment_target_value ("," deployment_target_value)*
deployment_target_value ::= "memory" | "disk"

# ==========================================
# SUBNET SPECIFIC RULES (IPv4 & IPv6 CIDR)
# ==========================================
subnet_key ::= "subnets" | "not_subnets"
subnet_filter ::= subnet_key ":(" subnet_value_list ")"
subnet_value_list ::= "=" subnet_value ("," subnet_value)*
subnet_value ::= ipv4_subnet | ipv6_subnet
ipv4_subnet ::= [0-9] [0-9]? [0-9]? "." [0-9] [0-9]? [0-9]? "." [0-9] [0-9]? [0-9]? "." [0-9] [0-9]? [0-9]? "/" [0-9] [0-9]?
ipv6_subnet ::= [0-9a-fA-F:]+ "/" [0-9] [0-9]? [0-9]?

# ==========================================
# NUMERIC RULES (No "=" operator)
# ==========================================
# Keys for performance, capacity, and counts.
numeric_keys ::= "cpu_count" | "not_cpu_count" | "mem" | "not_mem" | "cpu_speed" | "not_cpu_speed" | "link_speed" | "not_link_speed" | "physical_disk_count" | "not_physical_disk_count" | "total_storage" | "not_total_storage"
numeric_filter ::= numeric_keys ":(" numeric_value_list ")"
numeric_value_list ::= numeric_value ("," numeric_value)*
numeric_value ::= [0-9]+

# ==========================================
# GENERIC RULES (For the remaining 38 keys)
# ==========================================
generic_keys ::= "agent_name" | "arch" | "description" | "distro_series" | "domain" | "error_description" | "fabric_classes" | "fabrics" | "free_text" | "hostname" | "id" | "ip_addresses" | "mac_address" | "not_arch" | "not_distro_series" | "not_fabric_classes" | "not_fabrics" | "not_id" | "not_in_pool" | "not_in_zone" | "not_ip_addresses" | "not_osystem" | "not_owner" | "not_pod" | "not_pod_type" | "not_tags" | "not_vlans" | "osystem" | "owner" | "parent" | "pod" | "pod_type" | "pool" | "spaces" | "tags" | "vlans" | "workloads" | "zone"

generic_filter ::= generic_keys ":(" generic_value_list ")"
generic_value_list ::= "=" generic_value ("," generic_value)*
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
