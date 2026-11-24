"""Zero-cost mode: never infer billing status from an API key or model name."""


class FreeOnlyBlocked(RuntimeError):
    pass


def require_free_generation():
    # There is no reliable billing-status API in this application. Fail closed.
    raise FreeOnlyBlocked(
        "Yalnızca ücretsiz mod: Google projesinin faturalandırma durumu "
        "doğrulanamadığı için Gemini metin ve ses çağrıları kapalı. "
        "Metni yapıştırabilir ve dinleyip onayladığınız ses kaydını yükleyebilirsiniz."
    )
