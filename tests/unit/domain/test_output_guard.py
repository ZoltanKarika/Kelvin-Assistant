from kelvin_assistant.domain.output_guard import mask_secrets


def test_mask_bearer_token() -> None:
    text = (
        "Authorization: Bearer "
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ"
        ".SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    )
    expected = "Authorization: [BEARER_TOKEN_MASKED]"
    assert mask_secrets(text) == expected


def test_mask_pem_private_key() -> None:
    text = """some text before
-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEAl...
-----END RSA PRIVATE KEY-----
some text after"""
    expected = """some text before
[PRIVATE_KEY_MASKED]
some text after"""
    assert mask_secrets(text) == expected


def test_mask_postgres_url() -> None:
    text = "DB_URL=postgres://user:password123@host.com:5432/dbname"
    expected = "DB_URL=[POSTGRES_URL_MASKED]"
    assert mask_secrets(text) == expected


def test_mask_generic_db_connection_string() -> None:
    text = "DATABASE_URL=mysql://user:supersecret@db.example.com:3306/my_db"
    expected = "DATABASE_URL=[DB_CONNECTION_STRING_MASKED]db.example.com:3306/my_db"
    assert mask_secrets(text) == expected


def test_no_secrets_leaves_text_unchanged() -> None:
    text = "This is a normal sentence with no secrets."
    assert mask_secrets(text) == text


def test_mask_multiple_secrets() -> None:
    text = """Token: Bearer abc.def.ghi, and key:
-----BEGIN EC PRIVATE KEY-----
...
-----END EC PRIVATE KEY-----"""
    expected = """Token: [BEARER_TOKEN_MASKED], and key:
[PRIVATE_KEY_MASKED]"""
    assert mask_secrets(text) == expected


def test_mask_none_input() -> None:
    assert mask_secrets(None) is None
