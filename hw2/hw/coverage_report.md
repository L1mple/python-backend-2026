((.venv) ) nktnlx@nktnlx-14 python-backend-2026 % pytest -vv --cov=shop_api --cov-config=.coveragerc --cov-report=term-missing ./hw2/hw/
=============================================== test session starts ================================================
platform darwin -- Python 3.12.12, pytest-9.1.1, pluggy-1.6.0 -- /Users/nktnlx/Documents/github/python-backend-2026/.venv/bin/python3.12
cachedir: .pytest_cache
rootdir: /Users/nktnlx/Documents/github/python-backend-2026
configfile: pytest.ini
plugins: cov-7.1.0, asyncio-1.4.0, Faker-40.40.0, anyio-4.15.1
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 52 items                                                                                                 

hw2/hw/test_coverage.py::test_get_cart_not_found PASSED                                                      [  1%]
hw2/hw/test_coverage.py::test_add_to_cart_not_found_cart PASSED                                              [  3%]
hw2/hw/test_coverage.py::test_add_to_cart_not_found_item PASSED                                              [  5%]
hw2/hw/test_coverage.py::test_put_item_not_found PASSED                                                      [  7%]
hw2/hw/test_coverage.py::test_put_item_already_deleted PASSED                                                [  9%]
hw2/hw/test_coverage.py::test_patch_item_not_found PASSED                                                    [ 11%]
hw2/hw/test_coverage.py::test_delete_item_not_found PASSED                                                   [ 13%]
hw2/hw/test_coverage.py::test_add_item_increment_quantity PASSED                                             [ 15%]
hw2/hw/test_coverage.py::test_cart_ignores_deleted_items PASSED                                              [ 17%]
hw2/hw/test_coverage.py::test_get_carts_all_filters PASSED                                                   [ 19%]
hw2/hw/test_coverage.py::test_init_db_and_lifespan PASSED                                                    [ 21%]
hw2/hw/test_coverage.py::test_get_session PASSED                                                             [ 23%]
hw2/hw/test_coverage.py::test_models_representation PASSED                                                   [ 25%]
hw2/hw/test_homework2.py::test_post_cart PASSED                                                              [ 26%]
hw2/hw/test_homework2.py::test_get_cart[existing_empty_cart_id-False] PASSED                                 [ 28%]
hw2/hw/test_homework2.py::test_get_cart[existing_not_empty_cart_id-True] PASSED                              [ 30%]
hw2/hw/test_homework2.py::test_get_cart_list[query0-200] PASSED                                              [ 32%]
hw2/hw/test_homework2.py::test_get_cart_list[query1-200] PASSED                                              [ 34%]
hw2/hw/test_homework2.py::test_get_cart_list[query2-200] PASSED                                              [ 36%]
hw2/hw/test_homework2.py::test_get_cart_list[query3-200] PASSED                                              [ 38%]
hw2/hw/test_homework2.py::test_get_cart_list[query4-200] PASSED                                              [ 40%]
hw2/hw/test_homework2.py::test_get_cart_list[query5-200] PASSED                                              [ 42%]
hw2/hw/test_homework2.py::test_get_cart_list[query6-422] PASSED                                              [ 44%]
hw2/hw/test_homework2.py::test_get_cart_list[query7-422] PASSED                                              [ 46%]
hw2/hw/test_homework2.py::test_get_cart_list[query8-422] PASSED                                              [ 48%]
hw2/hw/test_homework2.py::test_get_cart_list[query9-422] PASSED                                              [ 50%]
hw2/hw/test_homework2.py::test_get_cart_list[query10-422] PASSED                                             [ 51%]
hw2/hw/test_homework2.py::test_get_cart_list[query11-422] PASSED                                             [ 53%]
hw2/hw/test_homework2.py::test_get_cart_list[query12-422] PASSED                                             [ 55%]
hw2/hw/test_homework2.py::test_post_item PASSED                                                              [ 57%]
hw2/hw/test_homework2.py::test_get_item PASSED                                                               [ 59%]
hw2/hw/test_homework2.py::test_get_item_list[query0-200] PASSED                                              [ 61%]
hw2/hw/test_homework2.py::test_get_item_list[query1-200] PASSED                                              [ 63%]
hw2/hw/test_homework2.py::test_get_item_list[query2-200] PASSED                                              [ 65%]
hw2/hw/test_homework2.py::test_get_item_list[query3-200] PASSED                                              [ 67%]
hw2/hw/test_homework2.py::test_get_item_list[query4-422] PASSED                                              [ 69%]
hw2/hw/test_homework2.py::test_get_item_list[query5-422] PASSED                                              [ 71%]
hw2/hw/test_homework2.py::test_get_item_list[query6-422] PASSED                                              [ 73%]
hw2/hw/test_homework2.py::test_get_item_list[query7-422] PASSED                                              [ 75%]
hw2/hw/test_homework2.py::test_get_item_list[query8-422] PASSED                                              [ 76%]
hw2/hw/test_homework2.py::test_put_item[body0-422] PASSED                                                    [ 78%]
hw2/hw/test_homework2.py::test_put_item[body1-422] PASSED                                                    [ 80%]
hw2/hw/test_homework2.py::test_put_item[body2-200] PASSED                                                    [ 82%]
hw2/hw/test_homework2.py::test_patch_item[deleted_item-body0-304] PASSED                                     [ 84%]
hw2/hw/test_homework2.py::test_patch_item[deleted_item-body1-304] PASSED                                     [ 86%]
hw2/hw/test_homework2.py::test_patch_item[deleted_item-body2-304] PASSED                                     [ 88%]
hw2/hw/test_homework2.py::test_patch_item[existing_item-body3-200] PASSED                                    [ 90%]
hw2/hw/test_homework2.py::test_patch_item[existing_item-body4-200] PASSED                                    [ 92%]
hw2/hw/test_homework2.py::test_patch_item[existing_item-body5-200] PASSED                                    [ 94%]
hw2/hw/test_homework2.py::test_patch_item[existing_item-body6-422] PASSED                                    [ 96%]
hw2/hw/test_homework2.py::test_patch_item[existing_item-body7-422] PASSED                                    [ 98%]
hw2/hw/test_homework2.py::test_delete_item PASSED                                                            [100%]

================================================= warnings summary =================================================
.venv/lib/python3.12/site-packages/fastapi/testclient.py:1
  /Users/nktnlx/Documents/github/python-backend-2026/.venv/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
================================================== tests coverage ==================================================
________________________________ coverage: platform darwin, python 3.12.12-final-0 _________________________________

Name                          Stmts   Miss  Cover   Missing
-----------------------------------------------------------
hw2/hw/shop_api/__init__.py       0      0   100%
hw2/hw/shop_api/database.py      19      0   100%
hw2/hw/shop_api/main.py         138      0   100%
hw2/hw/shop_api/models.py        20      0   100%
-----------------------------------------------------------
TOTAL                           177      0   100%
========================================== 52 passed, 1 warning in 17.76s ==========================================