"""Tests for SmartSDR protocol parser."""

from flexradiolog.radio.parser import ProtocolParser, parse_frequency_hz, parse_key_value_pairs


def test_parse_version_and_handle():
    msg_v = ProtocolParser.parse_line("V3.4.24.112\n")
    assert msg_v is not None
    assert msg_v.msg_type == "V"
    assert msg_v.attributes.get("version") == "3.4.24.112"

    msg_h = ProtocolParser.parse_line("H7F8E9D0A\r\n")
    assert msg_h is not None
    assert msg_h.msg_type == "H"
    assert msg_h.handle == "7F8E9D0A"


def test_parse_command_response():
    msg_r = ProtocolParser.parse_line("R1|0|\n")
    assert msg_r is not None
    assert msg_r.msg_type == "R"
    assert msg_r.seq == "1"
    assert msg_r.code == "0"

    msg_err = ProtocolParser.parse_line("R2|1000|Command failed\n")
    assert msg_err is not None
    assert msg_err.code == "1000"
    assert msg_err.attributes.get("message") == "Command failed"


def test_parse_client_status():
    line = "S0|client 0B3B59D0-9377-44E2-8BCF-BE4F9BEAA84D connected=1 ip=192.168.84.100 name=SmartSDR-Win station=HB9XYZ gui=1\n"
    msg = ProtocolParser.parse_line(line)
    assert msg is not None
    assert msg.msg_type == "S"
    assert msg.object_type == "client"
    assert msg.object_id == "0B3B59D0-9377-44E2-8BCF-BE4F9BEAA84D"
    assert msg.attributes["connected"] == "1"
    assert msg.attributes["ip"] == "192.168.84.100"
    assert msg.attributes["name"] == "SmartSDR-Win"
    assert msg.attributes["station"] == "HB9XYZ"
    assert msg.attributes["gui"] == "1"


def test_parse_interlock_status():
    line = "S0|interlock state=TRANSMITTING source=SW tx_client_handle=0x12345678 tx_allowed=1\n"
    msg = ProtocolParser.parse_line(line)
    assert msg is not None
    assert msg.msg_type == "S"
    assert msg.object_type == "interlock"
    assert msg.attributes["state"] == "TRANSMITTING"
    assert msg.attributes["source"] == "SW"
    assert msg.attributes["tx_client_handle"] == "0x12345678"


def test_parse_slice_status():
    line = "S0|slice 0 RF_frequency=14.074000 mode=USB tx=1 client_handle=0x12345678\n"
    msg = ProtocolParser.parse_line(line)
    assert msg is not None
    assert msg.msg_type == "S"
    assert msg.object_type == "slice"
    assert msg.object_id == "0"
    assert msg.attributes["rf_frequency"] == "14.074000"
    assert msg.attributes["mode"] == "USB"
    assert msg.attributes["tx"] == "1"


def test_frequency_conversion():
    assert parse_frequency_hz("14.074000") == 14_074_000
    assert parse_frequency_hz("7.100") == 7_100_000
    assert parse_frequency_hz("14074000") == 14_074_000
    assert parse_frequency_hz("14074") == 14_074_000
    assert parse_frequency_hz("0") == 0
    assert parse_frequency_hz("") == 0
