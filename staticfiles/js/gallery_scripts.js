document.addEventListener('DOMContentLoaded', function () {
    // Обрабатываем все ссылки на изображения
    document.querySelectorAll('a[href^="#image-link-"]').forEach(link => {
        link.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();

            const imageId = this.getAttribute('href').substring(1);
            const allImages = Array.from(document.querySelectorAll('[data-fancybox="gallery"]'));

            // Находим индекс нужного изображения
            const targetIndex = allImages.findIndex(img =>
                img.querySelector(`#${imageId}`) !== null
            );

            if (targetIndex !== -1) {
                // Собираем все данные галереи
                const galleryData = allImages.map(img => ({
                    src: img.href,
                    type: 'image',
                    caption: img.getAttribute('data-caption') || ''
                }));

                // Открываем галерею
                Fancybox.show(galleryData, {
                    startIndex: targetIndex,
                    groupAll: true
                });
            }
        });
    });

    Fancybox.bind('[data-fancybox="gallery"]', {
        Images: {
            zoom: {
                max: 10,
                wheel: true
            }
        },
        groupAll: true,
        Thumbs: {autoStart: false}
    });

    Fancybox.bind('[data-fancybox="preview-link"]', {
        buttons: [
            "zoom",
            "share",
            "slideShow",
            "fullScreen",
            "download",
            "thumbs",
            "close"
        ]
    });
});