from store.models import ItemInfo, ItemMapper, ItemOrm


def test_item_mapper_to_orm_roundtrip() -> None:
    info = ItemInfo(name="mapped", price=12.5, deleted=False)
    orm = ItemMapper.to_orm(info)
    assert isinstance(orm, ItemOrm)
    assert orm.name == "mapped"
    assert orm.price == 12.5
    assert orm.deleted is False

    info2 = ItemInfo(name="mapped-again", price=99.0, deleted=True)
    orm2 = ItemMapper.to_orm(info2, orm)
    assert orm2 is orm
    assert orm2.name == "mapped-again"
    assert orm2.price == 99.0
    assert orm2.deleted is True