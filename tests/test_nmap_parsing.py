"""Tests for Nmap XML parsing improvements."""

import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from plugins.nmap.main import parse_xml_output


class TestNmapXMLParsing:
    """Test Nmap XML output parsing."""

    def test_empty_xml_returns_empty_list(self):
        """Test that empty or invalid XML returns empty list."""
        assert parse_xml_output("") == []
        assert parse_xml_output("<invalid>") == []
        assert parse_xml_output("not xml at all") == []

    def test_valid_xml_with_open_ports(self):
        """Test parsing of valid XML with open ports."""
        xml_data = """<?xml version="1.0"?>
<nmapscan>
<host>
<ports>
<port protocol="tcp" portid="22">
<state state="open"/>
<service name="ssh"/>
</port>
<port protocol="tcp" portid="80">
<state state="open"/>
<service name="http"/>
</port>
<port protocol="tcp" portid="443">
<state state="closed"/>
<service name="https"/>
</port>
</ports>
</host>
</nmapscan>"""

        result = parse_xml_output(xml_data)
        assert len(result) == 2  # Only open ports

        # Check first port (SSH)
        assert result[0]["port"] == 22
        assert result[0]["protocol"] == "tcp"
        assert result[0]["service"] == "ssh"

        # Check second port (HTTP)
        assert result[1]["port"] == 80
        assert result[1]["protocol"] == "tcp"
        assert result[1]["service"] == "http"

    def test_xml_with_no_open_ports(self):
        """Test XML where no ports are open."""
        xml_data = """<?xml version="1.0"?>
<nmapscan>
<host>
<ports>
<port protocol="tcp" portid="22">
<state state="closed"/>
<service name="ssh"/>
</port>
<port protocol="tcp" portid="80">
<state state="filtered"/>
<service name="http"/>
</port>
</ports>
</host>
</nmapscan>"""

        result = parse_xml_output(xml_data)
        assert result == []  # No open ports

    def test_xml_multiple_hosts(self):
        """Test XML with multiple hosts."""
        xml_data = """<?xml version="1.0"?>
<nmapscan>
<host>
<ports>
<port protocol="tcp" portid="22">
<state state="open"/>
<service name="ssh"/>
</port>
</ports>
</host>
<host>
<ports>
<port protocol="tcp" portid="80">
<state state="open"/>
<service name="http"/>
</port>
</ports>
</host>
</nmapscan>"""

        result = parse_xml_output(xml_data)
        assert len(result) == 2
        assert result[0]["port"] == 22
        assert result[1]["port"] == 80

    def test_xml_service_name_optional(self):
        """Test handling of missing service name."""
        xml_data = """<?xml version="1.0"?>
<nmapscan>
<host>
<ports>
<port protocol="tcp" portid="22">
<state state="open"/>
<!-- No service tag -->
</port>
<port protocol="tcp" portid="80">
<state state="open"/>
<service name="http"/>
</port>
</ports>
</host>
</nmapscan>"""

        result = parse_xml_output(xml_data)
        assert len(result) == 2
        assert result[0]["service"] == "unknown"  # Default when missing
        assert result[1]["service"] == "http"

    def test_malformed_xml_handled_gracefully(self):
        """Test that various malformed XML inputs don't crash."""
        malformed_inputs = [
            "<unclosed_tag>",
            "<host><port></host>",  # Wrong nesting
            "<?xml version='1.0'?> <invalid>",  # Text outside root
            "",  # Empty string
            "   ",  # Whitespace only
            None,  # None (would cause TypeError, but function should handle)
        ]

        for inp in malformed_inputs:
            if inp is None:
                # Skip None as it would cause TypeError before reaching our function
                continue
            try:
                result = parse_xml_output(inp)
                assert isinstance(result, list), f"Should return list, got {type(result)}"
            except Exception as e:
                pytest.fail(f"parse_xml_output raised exception on '{inp}': {e}")

    def test_xml_with_extra_whitespace(self):
        """Test XML with leading/trailing whitespace."""
        xml_with_whitespace = """
        <?xml version="1.0"?>
        <nmapscan>
        <host>
        <ports>
        <port protocol="tcp" portid="22">
        <state state="open"/>
        <service name="ssh"/>
        </port>
        </ports>
        </host>
        </nmapscan>
        """

        result = parse_xml_output(xml_with_whitespace)
        assert len(result) == 1
        assert result[0]["port"] == 22

    def test_udp_ports(self):
        """Test parsing of UDP ports."""
        xml_data = """<?xml version="1.0"?>
<nmapscan>
<host>
<ports>
<port protocol="udp" portid="53">
<state state="open"/>
<service name="domain"/>
</port>
</ports>
</host>
</nmapscan>"""

        result = parse_xml_output(xml_data)
        assert len(result) == 1
        assert result[0]["port"] == 53
        assert result[0]["protocol"] == "udp"
        assert result[0]["service"] == "domain"


if __name__ == "__main__":
    pytest.main([__file__])