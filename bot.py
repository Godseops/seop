import discord
from discord.ext import commands
from discord.ui import Button, View
import random

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

recruit_states = {}

@bot.event
async def on_ready():
    print(f"✅ 봇 로그인됨: {bot.user}")

# 참가 등록 처리
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    channel_id = message.channel.id
    content = message.content.strip()

    if channel_id in recruit_states:
        state = recruit_states[channel_id]
        if state.get("recruiting") and content in ['ㅅ', '손', '참가']:
            name = message.author.display_name
            if name not in state["participants"]:
                state["participants"].append(name)
                await message.channel.send(
                    f"🙌 {name}님 참가 완료!\n현재 참가자 수: {len(state['participants'])}명"
                )
                if len(state["participants"]) == 10:
                    await message.channel.send("🎯 참가자 10명 모집 완료! 모두 모여주세요 🎉")
                    await start_team_leader_selection(message.channel)
            else:
                await message.channel.send(f"❗ {name}님은 이미 참가하셨어요.")
    await bot.process_commands(message)

@bot.command()
async def 내전(ctx):
    channel_id = ctx.channel.id
    recruit_states[channel_id] = {
        "participants": [],
        "recruiting": True,
        "team_captains": [],
        "teams": {1: [], 2: []},
        "draft_turn": 0,
        "pick_order": [],
        "drafting": False,
        "team_message": None
    }
    await ctx.send("📢 내전 모집합니다! 'ㅅ', '손', '참가'로 참가해 주세요!")

@bot.command()
async def 쫑(ctx):
    channel_id = ctx.channel.id
    if channel_id in recruit_states:
        recruit_states.pop(channel_id)
        await ctx.send("🧹 참가 정보 및 팀 구성 데이터를 초기화했습니다!")

@bot.command()
async def 취소(ctx):
    channel_id = ctx.channel.id
    name = ctx.author.display_name
    if channel_id in recruit_states:
        state = recruit_states[channel_id]
        if name in state["participants"]:
            state["participants"].remove(name)
            await ctx.send(
                f"🚫 {name}님 참가를 취소했습니다!\n현재 참가자 수: {len(state['participants'])}명"
            )
        else:
            await ctx.send(f"❗ {name}님은 현재 참가자가 아닙니다.")
    else:
        await ctx.send("❗ 이 채널에서는 내전이 진행 중이 아닙니다.")

# 팀장 선택
async def start_team_leader_selection(channel):
    channel_id = channel.id
    state = recruit_states[channel_id]
    state["recruiting"] = False

    view = View(timeout=None)

    for name in state["participants"]:
        button = Button(label=name, style=discord.ButtonStyle.primary)

        async def callback(interaction, n=name, b=button):
            if interaction.user.display_name != n:
                await interaction.response.send_message("🔒 본인만 자신의 버튼을 누를 수 있어요!", ephemeral=True)
                return

            if len(state["team_captains"]) >= 2:
                await interaction.response.send_message("❗ 이미 두 명의 팀장이 선택되었습니다.", ephemeral=True)
                return

            if n in state["team_captains"]:
                await interaction.response.send_message("❗ 이미 선택된 팀장입니다.", ephemeral=True)
                return

            state["team_captains"].append(n)
            b.disabled = True
            await interaction.response.edit_message(view=view)

            if len(state["team_captains"]) == 2:
                random.shuffle(state["team_captains"])
                first_team = random.choice([1, 2])
                if first_team == 1:
                    state["pick_order"] = [1, 2, 2, 1, 1, 2, 2, 1]
                else:
                    state["pick_order"] = [2, 1, 1, 2, 2, 1, 1, 2]
                await start_draft(channel, first_team)

        button.callback = callback
        view.add_item(button)

    await channel.send("🎯 참가자 중에서 팀장 두 명을 선택하세요.", view=view)

# 드래프트 시작
async def start_draft(channel, first_team):
    channel_id = channel.id
    state = recruit_states[channel_id]
    state["drafting"] = True
    participants = [p for p in state["participants"] if p not in state["team_captains"]]
    state["draft_turn"] = 0

    msg = await channel.send("🏅 팀장 선정 완료! 팀 구성 중입니다...")
    state["team_message"] = msg

    await update_team_message(channel, first_team)
    await send_draft_buttons(channel, participants)

# 팀 메시지 업데이트
async def update_team_message(channel, first_team=None):
    channel_id = channel.id
    state = recruit_states[channel_id]

    captain1 = state["team_captains"][0]
    captain2 = state["team_captains"][1]
    team1 = ', '.join(state["teams"][1]) if state["teams"][1] else '없음'
    team2 = ', '.join(state["teams"][2]) if state["teams"][2] else '없음'

    msg = (
        "🏅 팀장 선정 완료!\n\n"
        f"📕 1팀 팀장: {captain1} ({team1})\n"
        f"📘 2팀 팀장: {captain2} ({team2})"
    )

    if first_team is not None:
        msg += f"\n🎯 첫 번째 픽은 {'1팀' if first_team == 1 else '2팀'}부터 시작합니다!"

    await state["team_message"].edit(content=msg)

# 팀원 선택 버튼
async def send_draft_buttons(channel, available):
    channel_id = channel.id
    state = recruit_states[channel_id]

    if state["draft_turn"] >= len(state["pick_order"]):
        await finish_teams(channel)
        return

    team_num = state["pick_order"][state["draft_turn"]]
    captain = state["team_captains"][team_num - 1]

    view = View(timeout=None)
    for name in available:
        button = Button(label=name, style=discord.ButtonStyle.secondary)

        async def callback(interaction, n=name):
            if interaction.user.display_name != captain:
                await interaction.response.send_message("❗ 지금은 다른 팀장의 차례입니다.", ephemeral=True)
                return

            state["teams"][team_num].append(n)
            available.remove(n)
            state["draft_turn"] += 1

            await interaction.message.delete()
            await update_team_message(channel)
            await send_draft_buttons(channel, available)

        button.callback = callback
        view.add_item(button)

    await channel.send(f"🎯 {team_num}팀 ({captain}) 님, 팀원을 선택하세요:", view=view)

# 최종 팀 구성 출력
async def finish_teams(channel):
    channel_id = channel.id
    state = recruit_states[channel_id]

    captain1 = state["team_captains"][0]
    captain2 = state["team_captains"][1]
    team1 = state["teams"][1]
    team2 = state["teams"][2]

    msg = (
        "🎉 팀 구성 완료!\n\n"
        f"📕 1팀 (팀장: {captain1})\n" + '\n'.join(f"- {name}" for name in team1) + "\n\n" +
        f"📘 2팀 (팀장: {captain2})\n" + '\n'.join(f"- {name}" for name in team2)
    )

    await channel.send(msg)

# 봇 실행
bot.run("MTM2MTgyMjU2MTk2NDY1NDgwNA.GG9Hel.WRAhoeB7wEffIJhA_ECZ-XI-7gm_VIhiJeWT_E")
