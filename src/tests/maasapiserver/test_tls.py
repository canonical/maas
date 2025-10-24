# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import ast
import inspect
import textwrap

import uvicorn.protocols.http.h11_impl as h11_impl

from maasapiserver.tls import TLSPatchedH11Protocol


class TestTLSPatchedH11Protocol:
    def test_handle_events_is_identical_except_patch(self):
        """
        Verify that TLSPatchedH11Protocol.handle_events matches uvicorn’s
        H11Protocol.handle_events except for the TLS patch section.

        This test removes the patch section from the source before parsing,
        so it compares the actual code semantics, not formatting.

        Since we are using a different linter, the patched version also differs in the format. So the trick is to simply compare the
        ast after the patch is removed.
        """

        original_src = inspect.getsource(h11_impl.H11Protocol.handle_events)
        patched_src = inspect.getsource(TLSPatchedH11Protocol.handle_events)

        # Dedent to take them as standalone functions
        original_src = textwrap.dedent(original_src)
        patched_src = textwrap.dedent(patched_src)

        filtered_lines = []
        in_patch_block = False
        for line in patched_src.splitlines():
            if "### BEGIN PATCH" in line:
                in_patch_block = True
                continue
            elif "### END PATCH" in line:
                in_patch_block = False
                continue
            if not in_patch_block:
                filtered_lines.append(line)
        patched_src_clean = "\n".join(filtered_lines)

        original_ast = ast.parse(original_src)
        patched_ast = ast.parse(patched_src_clean)

        assert ast.dump(original_ast) == ast.dump(patched_ast), (
            "handle_events differs from uvicorn's version beyond the TLS patch."
        )
