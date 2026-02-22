from detector.settings import parse_args


def test_parse_args_defaults(monkeypatch):
    monkeypatch.setattr("sys.argv", ["prog"])
    settings = parse_args()

    assert settings.host == "127.0.0.1"
    assert settings.port == 5672
    assert settings.binding_keys == ["#"]
    assert settings.log_level == "INFO"
    assert settings.pg_dbname == "seismic"


def test_parse_args_custom_values(monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        [
            "prog",
            "--host",
            "mq.local",
            "--port",
            "5673",
            "--binding-key",
            "xx.*",
            "--binding-key",
            "yy.#",
            "--log-level",
            "debug",
            "--pg-db",
            "events",
        ],
    )
    settings = parse_args()

    assert settings.host == "mq.local"
    assert settings.port == 5673
    assert settings.binding_keys == ["xx.*", "yy.#"]
    assert settings.log_level == "DEBUG"
    assert settings.pg_dbname == "events"
