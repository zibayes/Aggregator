import torch
import torch.nn as nn
from torchvision import models, transforms
import numpy as np


class PyTorchImageClassifier:
    def __init__(self, model_path, class_names, img_size=224, device=None):
        self.class_names = class_names
        self.img_size = img_size
        self.device = device if device else torch.device('cuda' if torch.cuda.is_available() else 'cpu')

        self.model = self._initialize_model()
        self._load_weights(model_path)
        self.model.eval()
        self.transform = self._get_transform()

    def _initialize_model(self):
        """Создает EfficientNet модель"""
        model = models.efficientnet_b0(weights=None)
        model.classifier[1] = nn.Sequential(
            nn.Dropout(0.7),
            nn.Linear(1280, 512),
            nn.ReLU(),
            nn.Dropout(0.7),
            nn.Linear(512, len(self.class_names))
        )
        return model.to(self.device)

    def _load_weights(self, model_path):
        """Загружает веса с обработкой префиксов"""
        state_dict = torch.load(model_path, map_location=self.device, weights_only=True)

        # Удаляем префиксы _orig_mod. если есть
        new_state_dict = {}
        for key, value in state_dict.items():
            new_key = key.replace('_orig_mod.', '')
            new_state_dict[new_key] = value

        self.model.load_state_dict(new_state_dict, strict=False)
        print("PyTorch модель загружена")

    def _get_transform(self):
        return transforms.Compose([
            transforms.Resize(256),
            transforms.CenterCrop(self.img_size),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        ])

    def predict(self, pil_img):
        """Предсказывает класс изображения"""
        try:
            # Преобразуем PIL Image в tensor
            image_tensor = self.transform(pil_img).unsqueeze(0).to(self.device)

            with torch.no_grad():
                outputs = self.model(image_tensor)
                probabilities = torch.nn.functional.softmax(outputs, dim=1)
                probs = probabilities[0].cpu().numpy()

            predicted_class_idx = np.argmax(probs)
            confidence = probs[predicted_class_idx]
            print('ВАНГУЮ КЛАСС КАРТИНКИ: ' + str(self.class_names[predicted_class_idx]) + ' ' + str(confidence))

            return self.class_names[predicted_class_idx], confidence

        except Exception as e:
            print(f"Ошибка предсказания: {e}")
            return "Документы", 0.0
