import openai

# Замените YOUR_OPENAI_API_KEY на ваш реальный API-ключ
openai.api_key = "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"

models = openai.Model.list()
for model in models.data:
    print(model.id)
