from recon_agent.__main__ import main


def test_cli_reports_not_implemented(capsys):
    assert main([]) == 1
    assert "not implemented" in capsys.readouterr().out
