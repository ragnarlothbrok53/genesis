from genesis_cli.compose import render_compose


def test_service_environment_is_read_generically():
    services = [
        {
            "name": "widgetdb",
            "image": "widgetdb:1",
            "environment": {"WIDGET_MODE": "fast", "WIDGET_KEY": "${WIDGET_KEY:-secret}"},
        }
    ]
    compose = render_compose("proj", services, [])
    assert "  widgetdb:" in compose
    assert '      WIDGET_KEY: "${WIDGET_KEY:-secret}"' in compose
    assert '      WIDGET_MODE: "fast"' in compose


def test_service_without_environment_omits_block():
    services = [{"name": "plain", "image": "plain:1"}]
    compose = render_compose("proj", services, [])
    lines = compose.splitlines()
    idx = lines.index("  plain:")
    assert lines[idx + 1] == "    image: plain:1"
    assert lines[idx + 2] == ""
