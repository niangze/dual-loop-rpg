"""
演示：三大核心数据结构作为全局变量调用。
"""
from core.game_state import player, npcs, dungeon
from core.models import Item, Rank


def show_state():
    print("=" * 50)
    print("【玩家】", player)
    print("  金钱:", player.money, "| Rank:", player.rank.value)
    print("  背包:", [f"{i.name}x{i.quantity}" for i in player.inventory])
    for n in npcs:
        print(f"【NPC】{n.name} 性格={n.personality_tags} 好感={n.favorability} 记忆={n.memory}")
    for f in dungeon:
        print(f"【地下城 {f.floor_number}F】怪物池={[m.name for m in f.monster_pool]} "
              f"掉落={[d.name for d in f.drop_table]} 通关={f.cleared}")
    print("=" * 50)


if __name__ == "__main__":
    print(">>> 初始状态")
    show_state()

    player.hp -= 20
    player.add_item(Item(item_id="potion", name="初级药水", quantity=2))
    player.rank = Rank.SILVER
    npcs[0].change_favorability(5)
    npcs[0].remember("一起喝过酒")
    dungeon[0].cleared = True

    print("\n>>> 修改后状态")
    show_state()
    print("玩家当前生命:", player.hp, "/", player.max_hp)
    print("艾琳好感度:", npcs[0].favorability, "| 记忆:", npcs[0].memory)
    print("第 1 层是否通关:", dungeon[0].cleared)
