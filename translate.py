from google.cloud import translate_v2 as translate
from google.oauth2 import service_account


class Translate:
    def __init__(self):
        self.credentials = service_account.Credentials.from_service_account_file(
            "service_account.json"
        )
        self.client = translate.Client(credentials=self.credentials)

    def translate_to_en(self, text):
        if self.client.detect_language(text)["language"] == "en":
            return text
        result = self.client.translate(text, source_language="ja", target_language="en")
        return result["translatedText"]


if __name__ == "__main__":
    translate = Translate()
    print(translate.translate_to_en("水"))
