# JSON-LD шаблоны (Schema.org) под РФ-реалии

Готовые вставляемые сниппеты — не пересказывай их, а бери и адаптируй под данные конкретного клиента. Все примеры валидны сами по себе; перед сдачей клиенту прогони итоговый код через:
- **Яндекс:** «Валидатор микроразметки» — встроенный инструмент внутри Яндекс.Вебмастера (не отдельный сайт, ищи в левом меню Вебмастера), проверяет соответствие и schema.org, и специфичным требованиям Яндекса
- **Google:** Rich Results Test / Schema Markup Validator (schema.org)

Для Tilda часть разметки (Organization, базовый Product) генерируется автоматически из настроек сайта — проверяй, что она реально включена, а не просто предполагай. FAQPage и кастомные поля обычно нужно вставлять вручную через Zero Block/HTML-блок — за деталями вставки зови скилл `tilda-helper`.

**О чём стоит сразу предупредить клиента:** сама по себе валидная разметка не гарантирует визуальный сниппет в выдаче — решение показывать его принимает поисковик, а не наличие JSON-LD. В частности, у Google `HowTo` rich results отключены с августа 2023 (мобайл и десктоп), а `FAQ` rich results с мая 2026 отключены полностью для всех сайтов (даже для ранее исключённых гос./мед. площадок) — поэтому шаблона `HowTo` здесь нет: используй его структуру (шаги) в самом видимом контенте страницы ради GEO и юзабилити, а не ради невидимого JSON-LD ради сниппета, которого не будет. `FAQPage` ниже всё равно приводится и его стоит ставить — но объясняй клиенту его текущую пользу честно: структурированные факты для ИИ-парсинга и (там, где применимо) Яндекса, а не «попадание в сниппет Google».

## Organization

Базовая разметка организации — ставится на главной и в футере/head сквозным блоком. Обязательно заполняй `sameAs` реальными профилями (Яндекс.Бизнес, VK, Telegram) — это прямой сигнал бренд-авторитета.

```json
{
  "@context": "https://schema.org",
  "@type": "Organization",
  "name": "ООО «Название компании»",
  "url": "https://example.ru",
  "logo": "https://example.ru/logo.png",
  "telephone": "+7-495-000-00-00",
  "email": "info@example.ru",
  "address": {
    "@type": "PostalAddress",
    "streetAddress": "ул. Примерная, д. 1",
    "addressLocality": "Москва",
    "postalCode": "101000",
    "addressCountry": "RU"
  },
  "taxID": "7700000000",
  "sameAs": [
    "https://yandex.ru/maps/org/12345",
    "https://vk.com/example",
    "https://t.me/example"
  ]
}
```

## LocalBusiness

Для сайтов с офлайн-точкой (шоурум, офис приёма клиентов, филиалы). `priceRange` — условный индикатор ценового сегмента (`₽`/`₽₽`/`₽₽₽`), не путать с конкретными ценами товаров.

```json
{
  "@context": "https://schema.org",
  "@type": "LocalBusiness",
  "name": "Название",
  "image": "https://example.ru/photo-office.jpg",
  "priceRange": "₽₽",
  "telephone": "+7-495-000-00-00",
  "address": {
    "@type": "PostalAddress",
    "streetAddress": "ул. Примерная, д. 1",
    "addressLocality": "Москва",
    "postalCode": "101000",
    "addressCountry": "RU"
  },
  "geo": {
    "@type": "GeoCoordinates",
    "latitude": 55.751244,
    "longitude": 37.618423
  },
  "openingHoursSpecification": [
    {
      "@type": "OpeningHoursSpecification",
      "dayOfWeek": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
      "opens": "09:00",
      "closes": "18:00"
    }
  ],
  "aggregateRating": {
    "@type": "AggregateRating",
    "ratingValue": "4.8",
    "reviewCount": "124"
  }
}
```

`aggregateRating` вставляй только если рейтинг реально собран (отзывы на сайте/агрегаторах) — фиктивный рейтинг нарушает правила структурированных данных Google и может привести к ручным санкциям.

## FAQPage

Ставь на страницы с реальным блоком «Вопрос-Ответ» в видимом контенте — разметка должна дублировать то, что пользователь видит на странице, а не добавлять невидимые вопросы только ради сниппета.

```json
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    {
      "@type": "Question",
      "name": "Сколько стоит услуга под ключ?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "Стоимость от 25 000 ₽ и зависит от объёма работ. Точную смету считаем после бесплатного замера — обычно в течение 1 рабочего дня."
      }
    },
    {
      "@type": "Question",
      "name": "Какие сроки выполнения?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "Стандартный срок — от 3 до 10 рабочих дней в зависимости от сложности проекта. Точный срок фиксируется в договоре после замера."
      }
    }
  ]
}
```

Держи каждый ответ в пределах 40–80 слов (см. [точная цитируемость](geo-ai-poisk.md#точная-цитируемость-текстовых-блоков)) — так он одинаково хорошо подходит и для голосового ответа Алисы, и для цитирования в ChatGPT/Perplexity. Сам JSON-LD с мая 2026 не даёт визуального FAQ-сниппета в Google (см. предупреждение в начале файла) — но видимый на странице текст ответа по-прежнему может попасть в обычный featured snippet, это не зависит от разметки.

## Product / Offer

`priceCurrency` для РФ — всегда `RUB`. `availability` бери из реального остатка, не ставь `InStock` по умолчанию, если товар может закончиться.

```json
{
  "@context": "https://schema.org",
  "@type": "Product",
  "name": "Название товара",
  "description": "Короткое описание товара с ключевыми характеристиками.",
  "image": "https://example.ru/product.jpg",
  "sku": "ART-00123",
  "brand": {
    "@type": "Brand",
    "name": "Название бренда"
  },
  "offers": {
    "@type": "Offer",
    "price": "5000",
    "priceCurrency": "RUB",
    "availability": "https://schema.org/InStock",
    "url": "https://example.ru/catalog/product-00123"
  }
}
```

## Article + Person (авторство, E-E-A-T)

Обязательно для экспертных статей — модель охотнее доверяет и цитирует контент с явным, проверяемым авторством.

```json
{
  "@context": "https://schema.org",
  "@type": "Article",
  "headline": "Заголовок статьи",
  "datePublished": "2026-06-01",
  "dateModified": "2026-08-02",
  "author": {
    "@type": "Person",
    "name": "Имя Фамилия",
    "jobTitle": "Руководитель SEO-отдела",
    "url": "https://example.ru/team/author"
  },
  "publisher": {
    "@type": "Organization",
    "name": "Название компании",
    "logo": {
      "@type": "ImageObject",
      "url": "https://example.ru/logo.png"
    }
  }
}
```
