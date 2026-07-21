from ocr.engine import words_from_paddle_result
from ocr.models import OCRWord

def test_words_from_paddle_result_maps_polys_to_bboxes():
    result = {
        "rec_texts": ["Hello", "World"],
        "rec_scores": [0.99, 0.88],
        "rec_polys": [
            [[10, 20], [50, 20], [50, 40], [10, 40]],   # x0,y0,x1,y1 = 10,20,50,40
            [[60, 22], [90, 22], [90, 38], [60, 38]],
        ],
    }
    words = words_from_paddle_result(result)
    assert [w.text for w in words] == ["Hello", "World"]
    assert isinstance(words[0], OCRWord)
    assert (words[0].bbox.x0, words[0].bbox.y0, words[0].bbox.x1, words[0].bbox.y1) == (10, 20, 50, 40)
    assert words[0].confidence == 0.99

def test_words_from_paddle_result_handles_empty():
    assert words_from_paddle_result({"rec_texts": [], "rec_scores": [], "rec_polys": []}) == []
