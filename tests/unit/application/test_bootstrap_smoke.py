from bulbopt.app.main import build_cli_banner


def test_build_cli_banner_contains_product_name() -> None:
    banner = build_cli_banner()

    assert "BulbOpt Desktop" in banner
    assert "STL-first" in banner