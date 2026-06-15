from __future__ import annotations

import pytest
from pydantic import ValidationError

from core.models import Candidate, Product, Review, VideoAsset, VocItem, VoC


def test_product_valid_and_serializes():
    product = Product(
        nmId=12345678,
        imtId=87654321,
        name="Фен Dyson",
        brand="Dyson",
        price=1990.0,
        feedbacks=120,
        rating=4.6,
        img_url="https://basket-01.wbbasket.ru/vol1/part1/1/1/images/big/1.jpg",
        url="https://www.wildberries.ru/catalog/12345678/detail.aspx",
    )

    assert product.nmId == 12345678
    assert product.rating == 4.6

    dumped = product.model_dump()
    assert dumped["name"] == "Фен Dyson"

    as_json = product.model_dump_json()
    assert "Фен Dyson" in as_json

    restored = Product.model_validate_json(as_json)
    assert restored.nmId == product.nmId
    assert restored.imtId == product.imtId


def test_product_optional_url_fields_default_none():
    product = Product(nmId=1, imtId=2, name="n", brand="b")

    assert product.img_url is None
    assert product.url is None
    assert product.price == 0.0
    assert product.feedbacks == 0
    assert product.rating == 0.0


def test_product_rejects_bad_numeric_constraints():
    with pytest.raises(ValidationError):
        Product(nmId=1, imtId=2, name="n", brand="b", rating=6)
    with pytest.raises(ValidationError):
        Product(nmId=1, imtId=2, name="n", brand="b", rating=-0.5)
    with pytest.raises(ValidationError):
        Product(nmId=1, imtId=2, name="n", brand="b", feedbacks=-5)
    with pytest.raises(ValidationError):
        Product(nmId=1, imtId=2, name="n", brand="b", price=-10)


def test_review_valid_and_photo_urls_defaults_to_list():
    review = Review(id="100", nmId=12345678, text="Хороший фен", rating=5, date="2024-05-01")

    assert review.photo_urls == []
    assert review.pros == []
    assert review.cons == []
    assert review.video_url is None

    review_full = Review(
        id="101",
        nmId=12345678,
        text="Огонь",
        rating=4,
        date="2024-05-02",
        pros=["мощный"],
        cons=["тяжёлый"],
        photo_urls=["https://x/a.jpg", "https://x/b.jpg"],
        video_url="https://v/x.mp4",
    )
    assert review_full.pros == ["мощный"]
    assert len(review_full.photo_urls) == 2
    assert review_full.video_url.endswith(".mp4")


def test_review_allows_missing_nmid_and_date():
    review = Review(id="abc", text="без товара и даты", rating=4)

    assert review.nmId is None
    assert review.date == ""


def test_candidate_similarity_in_range():
    candidate = Candidate(
        site="alibaba",
        title="Hair dryer",
        url="https://m.alibaba.com/p/1",
        thumb_url="https://t/1.jpg",
        price=5.0,
        similarity=0.85,
        has_video=True,
    )
    assert 0.0 <= candidate.similarity <= 1.0

    Candidate(site="x", title="t", thumb_url="u", similarity=0.0)
    Candidate(site="x", title="t", thumb_url="u", similarity=1.0)

    with pytest.raises(ValidationError):
        Candidate(site="x", title="t", thumb_url="u", similarity=1.5)
    with pytest.raises(ValidationError):
        Candidate(site="x", title="t", thumb_url="u", similarity=-0.1)
    with pytest.raises(ValidationError):
        Candidate(site="x", title="t", thumb_url="u", price=-1)


def test_voc_creates_with_all_lists():
    voc = VoC(
        боли=[VocItem(text="горит", frequency=3)],
        желания=[VocItem(text="холодный воздух", frequency=2)],
        страхи=[VocItem(text="сломается за месяц", frequency=1)],
        триггеры=[VocItem(text="увидел в reels", frequency=1)],
        восторги=[VocItem(text="мощный мотор", frequency=4)],
        возражения=[VocItem(text="дорого", frequency=2)],
        язык_клиента=[VocItem(text="дует как извержение", frequency=1)],
    )

    assert len(voc.боли) == 1
    assert voc.боли[0].text == "горит"
    assert voc.желания[0].frequency == 2
    assert len(voc.восторги) == 1

    empty = VoC()
    assert empty.страхи == []
    assert empty.язык_клиента == []

    dumped = voc.model_dump()
    assert dumped["восторги"][0]["text"] == "мощный мотор"
    assert dumped["возражения"][0]["frequency"] == 2

    restored = VoC.model_validate_json(voc.model_dump_json())
    assert restored.боли[0].text == "горит"


def test_video_asset_accepts_only_known_sources():
    wb_asset = VideoAsset(
        source="wb_review",
        nmId=12345678,
        local_path="output/video/12345678/wb_review_1.mp4",
        src_url="https://feedbacks.video/x.mp4",
    )
    assert wb_asset.source == "wb_review"
    assert wb_asset.description is None

    china_asset = VideoAsset(
        source="china",
        nmId=12345678,
        local_path="output/video/12345678/china_1.mp4",
        src_url="https://cloud.video.taobao.com/y.mp4",
        description="полочное видео карточки",
    )
    assert china_asset.source == "china"
    assert china_asset.description == "полочное видео карточки"

    with pytest.raises(ValidationError):
        VideoAsset(
            source="youtube",
            nmId=1,
            local_path="output/x.mp4",
            src_url="https://y",
        )
