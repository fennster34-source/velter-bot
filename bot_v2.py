import discord
from discord import app_commands
import asyncio
from dotenv import load_dotenv
import os

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

WELCOME_CHANNEL_NAME = "👋〢welcome"

invite_cache = {}

STAFF_ROLES = [
    "Dev. Team",
    "Director",
    "Head Admin",
    "Senior Admin",
    "Administrator",
    "Moderator",
    "Game Support"
]


def has_staff_role(member: discord.Member) -> bool:
    if member.guild_permissions.administrator:
        return True
    return any(role.name in STAFF_ROLES for role in member.roles)


class MyBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True  # Developer Portal -> Bot -> Message Content Intent
        intents.members = True          # Developer Portal -> Bot -> Server Members Intent
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        self.add_view(TicketMenuView())
        self.add_view(CloseTicketView())
        await self.tree.sync()
        print("Slash komande su sinhronizovane.")

    async def on_ready(self):
        print(f"Bot je ulogovan kao {self.user} (ID: {self.user.id})")
        for guild in self.guilds:
            try:
                invite_cache[guild.id] = {inv.code: inv.uses for inv in await guild.invites()}
            except Exception:
                pass


bot = MyBot()


async def open_ticket_channel(guild, user, ticket_type, embed_info: discord.Embed):
    channel_name = f"ticket-{ticket_type}-{user.name}".lower().replace(" ", "-")

    existing = discord.utils.get(guild.text_channels, name=channel_name)
    if existing:
        return None, existing

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
        guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
    }
    for role_name in STAFF_ROLES:
        role = discord.utils.get(guild.roles, name=role_name)
        if role:
            overwrites[role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_channels=True
            )

    category = discord.utils.get(guild.categories, name="ASKQ & REPORT")
    channel = await guild.create_text_channel(
        name=channel_name,
        overwrites=overwrites,
        category=category
    )

    await channel.send(embed=embed_info, view=CloseTicketView())

    staff_mentions = []
    for role_name in STAFF_ROLES:
        role = discord.utils.get(guild.roles, name=role_name)
        if role:
            staff_mentions.append(role.mention)
    if staff_mentions:
        await channel.send(" ".join(staff_mentions))

    return channel, None


class AskModal(discord.ui.Modal, title="❓ Ask Ticket"):
    nick = discord.ui.TextInput(
        label="Tvoj nick na serveru",
        placeholder="npr. Marko_Markovic",
        required=True,
        max_length=50
    )
    pitanje = discord.ui.TextInput(
        label="Šta ti treba od pomoći?",
        placeholder="Opiši što detaljnije...",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=500
    )

    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(title="❓ ASK TICKET", color=0x00C853)
        embed.add_field(name="👤 Korisnik", value=interaction.user.mention, inline=True)
        embed.add_field(name="🎮 Nick na serveru", value=self.nick.value, inline=True)
        embed.add_field(name="❓ Šta treba pomoći", value=self.pitanje.value, inline=False)
        embed.set_footer(text="Klikni dugme ispod da zatvoriš ticket kada završiš.")

        channel, existing = await open_ticket_channel(interaction.guild, interaction.user, "ask", embed)
        if existing:
            await interaction.response.send_message(f"❌ Već imaš otvoren ticket: {existing.mention}", ephemeral=True)
        else:
            await interaction.response.send_message(f"✅ Ticket je otvoren: {channel.mention}", ephemeral=True)


class ReportModal(discord.ui.Modal, title="📋 Report Ticket"):
    nick = discord.ui.TextInput(
        label="Tvoj nick na serveru",
        placeholder="npr. Marko_Markovic",
        required=True,
        max_length=50
    )
    reported_nick = discord.ui.TextInput(
        label="Ime_Prezime igrača kojeg prijaviš",
        placeholder="npr. Stefan_Stefanovic",
        required=True,
        max_length=50
    )
    razlog = discord.ui.TextInput(
        label="Razlog prijave",
        placeholder="Opiši što detaljnije šta se desilo...",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=500
    )

    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(title="📋 REPORT TICKET", color=0xFF4444)
        embed.add_field(name="👤 Podnosilac", value=interaction.user.mention, inline=True)
        embed.add_field(name="🎮 Tvoj nick", value=self.nick.value, inline=True)
        embed.add_field(name="🚨 Prijavljeni igrač", value=self.reported_nick.value, inline=True)
        embed.add_field(name="📄 Razlog prijave", value=self.razlog.value, inline=False)
        embed.set_footer(text="Klikni dugme ispod da zatvoriš ticket kada završiš.")

        channel, existing = await open_ticket_channel(interaction.guild, interaction.user, "report", embed)
        if existing:
            await interaction.response.send_message(f"❌ Već imaš otvoren ticket: {existing.mention}", ephemeral=True)
        else:
            await interaction.response.send_message(f"✅ Ticket je otvoren: {channel.mention}", ephemeral=True)


class TicketMenuView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📋 Report", style=discord.ButtonStyle.danger, custom_id="ticket_report")
    async def report_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ReportModal())

    @discord.ui.button(label="❓ Ask", style=discord.ButtonStyle.success, custom_id="ticket_ask")
    async def ask_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AskModal())


class CloseTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔒 Zatvori ticket", style=discord.ButtonStyle.secondary, custom_id="ticket_close")
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🔒 Ticket zatvoren",
            description=f"Ticket je zatvorio {interaction.user.mention}. Kanal će biti obrisan za 5 sekundi.",
            color=0x808080
        )
        await interaction.response.send_message(embed=embed)
        await asyncio.sleep(5)
        await interaction.channel.delete()


@bot.tree.command(name="ticketstart", description="Pošalje embed sa ticket sistemom u trenutni kanal")
async def ticketstart(interaction: discord.Interaction):
    if not has_staff_role(interaction.user):
        await interaction.response.send_message("❌ Nemaš dozvolu da koristiš ovu komandu!", ephemeral=True)
        return
    embed = discord.Embed(
        title="🎫 TICKET SISTEM",
        description=(
            "Ukoliko imaš problem ili pitanje, otvori ticket klikom na odgovarajuće dugme ispod.\n\n"
            "📋 **Report** — Prijavi igrača ili problem na serveru\n"
            "❓ **Ask** — Postavi pitanje staff timu\n\n"
            "⚠️ Molimo te da ne otvараš ticket bez razloga."
        ),
        color=0x00C853
    )
    embed.set_footer(text="Velter Roleplay | Ticket Sistem")
    await interaction.response.send_message("✅ Ticket sistem je pokrenut!", ephemeral=True)
    await interaction.channel.send(embed=embed, view=TicketMenuView())


@bot.tree.command(name="pravilastart", description="Pošalje embed sa pravilima servera u trenutni kanal")
async def pravilastart(interaction: discord.Interaction):
    if not has_staff_role(interaction.user):
        await interaction.response.send_message("❌ Nemaš dozvolu da koristiš ovu komandu!", ephemeral=True)
        return
    embed = discord.Embed(
        title="💚 VELTER ROLEPLAY | DISCORD PRAVILA 💚",
        description="Dobrodošli na **Velter Roleplay** Discord zajednicu 💚\nMolimo sve članove da poštuju pravila kako bi server bio prijatan, organizovan i aktivan.",
        color=0x00C853
    )
    embed.add_field(
        name="💚 1. OPŠTA PRAVILA",
        value=(
            "💚 Poštuj sve članove servera\n"
            "⚠️ Zabranjeno vređanje, rasizam i diskriminacija\n"
            "🛡️ Poštuj administraciju i njihove odluke\n"
            "🚫 Bez izazivanja svađa i nepotrebne drame\n"
            "📉 Spam i flood nisu dozvoljeni"
        ),
        inline=False
    )
    embed.add_field(
        name="💬 2. PONAŠANJE NA DISCORDU",
        value=(
            "💚 Koristi kanale za njihovu namenu\n"
            "🔞 NSFW sadržaj je strogo zabranjen\n"
            "📢 Reklamiranje bez dozvole nije dozvoljeno\n"
            "❗ Nemoj tagovati staff bez potrebe\n"
            "✍️ Piši kulturno i razumljivo"
        ),
        inline=False
    )
    embed.add_field(
        name="🎧 3. VOICE CHAT PRAVILA",
        value=(
            "🔊 Bez deranja i prevelike buke\n"
            "🎵 Zabranjeno puštanje muzike bez dozvole\n"
            "🤝 Poštuj ostale u voice kanalima\n"
            "🚫 Trollovanje u voice-u nije dozvoljeno"
        ),
        inline=False
    )
    embed.add_field(
        name="🛡️ 4. ADMINISTRACIJA",
        value=(
            "💚 Staff tim ima pravo da opomene ili kazni članove\n"
            "⚖️ Raspravljanje sa adminima javno nije dozvoljeno\n"
            "🎫 Žalbe se šalju isključivo preko ticket sistema\n"
            "📌 Odluke staff tima su konačne"
        ),
        inline=False
    )
    embed.add_field(
        name="🚫 5. ZABRANJENO JE",
        value=(
            "❌ Spam i bespotrebne poruke\n"
            "❌ Vređanje i provokacije\n"
            "🔞 NSFW sadržaj\n"
            "💸 Scam i prevare\n"
            "🔒 Deljenje tuđih ličnih podataka"
        ),
        inline=False
    )
    embed.add_field(
        name="⚠️ 6. KAZNE",
        value=(
            "Kršenje pravila može dovesti do:\n"
            "🟡 Warn\n"
            "🔇 Mute\n"
            "👢 Kick\n"
            "⛔ Ban"
        ),
        inline=False
    )
    embed.add_field(
        name="💚 7. CILJ ZAJEDNICE",
        value=(
            "Naš cilj je da zajedno napravimo:\n"
            "💚 aktivnu i zdravu zajednicu\n"
            "🌍 prijateljsku atmosferu\n"
            "🤝 poštovanje među članovima\n"
            "🎮 kvalitetan i uređen Discord server"
        ),
        inline=False
    )
    embed.set_footer(text="💚 Hvala ti što si deo Velter Roleplay zajednice i što pomažeš da server bude bolji za sve!")
    await interaction.response.send_message("✅ Pravila su poslata!", ephemeral=True)
    await interaction.channel.send(embed=embed)



class ObavestenieModal(discord.ui.Modal, title="📢 Novo obaveštenje"):
    naslov = discord.ui.TextInput(
        label="Naslov obaveštenja",
        placeholder="npr. Važno obaveštenje!",
        required=True,
        max_length=100
    )
    tekst = discord.ui.TextInput(
        label="Tekst obaveštenja",
        placeholder="Upiši tekst koji želiš da pošalješ...",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=2000
    )

    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title=f"📢 {self.naslov.value}",
            description=self.tekst.value,
            color=0x00C853
        )
        embed.set_footer(text=f"Obaveštenje poslao: {interaction.user.name}")
        await interaction.response.send_message("✅ Obaveštenje je poslato!", ephemeral=True)
        await interaction.channel.send("@here", embed=embed)


@bot.tree.command(name="new", description="Pošalje embed obaveštenje u trenutni kanal")
async def new(interaction: discord.Interaction):
    if not has_staff_role(interaction.user):
        await interaction.response.send_message("❌ Nemaš dozvolu da koristiš ovu komandu!", ephemeral=True)
        return
    await interaction.response.send_modal(ObavestenieModal())


IMAGE_CHANNEL_NAME = "「📸」images-from-server"
LOG_CHANNEL_NAME = "💾〢logs"


async def get_log_channel(guild: discord.Guild):
    return discord.utils.get(guild.text_channels, name=LOG_CHANNEL_NAME)


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    if message.channel.name == IMAGE_CHANNEL_NAME:
        if not message.attachments:
            await message.delete()


@bot.event
async def on_message_delete(message: discord.Message):
    if message.author.bot:
        return
    log = await get_log_channel(message.guild)
    if not log:
        return
    embed = discord.Embed(
        title="🗑️ Poruka obrisana",
        color=0xFF4444,
        timestamp=discord.utils.utcnow()
    )
    embed.add_field(name="👤 Korisnik", value=f"{message.author.mention} (`{message.author}`)", inline=True)
    embed.add_field(name="📌 Kanal", value=message.channel.mention, inline=True)
    embed.add_field(name="💬 Sadržaj", value=message.content or "*[bez teksta / samo fajl]*", inline=False)
    embed.set_footer(text=f"ID korisnika: {message.author.id}")
    await log.send(embed=embed)


@bot.event
async def on_message_edit(before: discord.Message, after: discord.Message):
    if before.author.bot:
        return
    if before.content == after.content:
        return
    log = await get_log_channel(before.guild)
    if not log:
        return
    embed = discord.Embed(
        title="✏️ Poruka izmenjena",
        color=0xFFA500,
        timestamp=discord.utils.utcnow()
    )
    embed.add_field(name="👤 Korisnik", value=f"{before.author.mention} (`{before.author}`)", inline=True)
    embed.add_field(name="📌 Kanal", value=before.channel.mention, inline=True)
    embed.add_field(name="📝 Pre izmene", value=before.content or "*prazno*", inline=False)
    embed.add_field(name="📝 Nakon izmene", value=after.content or "*prazno*", inline=False)
    embed.set_footer(text=f"ID korisnika: {before.author.id}")
    await log.send(embed=embed)


@bot.event
async def on_member_join(member: discord.Member):
    guild = member.guild

    # Automatsko dodeljivanje "Member" role
    member_role = discord.utils.get(guild.roles, name="Member")
    if member_role:
        try:
            await member.add_roles(member_role, reason="Auto-role on join")
            print(f"Dodeljena Member rola: {member.name}")
        except discord.Forbidden:
            print(f"Nemam permisije da dodelim Member rolu: {member.name}")
        except Exception as e:
            print(f"Greška pri dodeli Member role: {e}")
    else:
        print("Rola 'Member' ne postoji na serveru")

    # DM dobrodošlice korisniku
    try:
        dm_embed = discord.Embed(
            title="Dobrodošao na Velter 🌍",
            description=(
                f"Ćao {member.name}, dobrodošao na **Velter Discord Server**!\n\n"
                "🚀 Ovo nije običan server.\n"
                "Ovo je nova era SA-MP / OpenMP zajednice.\n\n"
                "🎮 Spremi se za potpuno novi GTA multiplayer doživljaj.\n"
                "⚡ Sistem, gameplay i ideje koje menjaju sve što znaš o SAMP-u.\n\n"
                "📌 Prati info kanal i pripremi se za launch!"
            ),
            color=0x2b2d31,
        )
        dm_embed.set_footer(text="Velter Roleplay • Nova era multiplayera")
        if guild.icon:
            dm_embed.set_thumbnail(url=guild.icon.url)
        await member.send(embed=dm_embed)
    except Exception:
        print(f"Ne mogu poslati DM korisniku: {member.name}")

    inviter = None
    try:
        new_invites = {inv.code: inv.uses for inv in await guild.invites()}
        cached = invite_cache.get(guild.id, {})
        for code, uses in new_invites.items():
            if uses > cached.get(code, 0):
                inv_obj = discord.utils.get(await guild.invites(), code=code)
                if inv_obj and inv_obj.inviter:
                    inviter = inv_obj.inviter
                break
        invite_cache[guild.id] = new_invites
    except Exception:
        pass

    welcome_channel = discord.utils.get(guild.text_channels, name=WELCOME_CHANNEL_NAME)
    if welcome_channel:
        embed = discord.Embed(
            title="💚 Dobrodošao na Velter Roleplay!",
            description=(
                f"Zdravo {member.mention}, dobrodošao na server! 🎉\n\n"
                f"{'Pozvao te: ' + inviter.mention if inviter else ''}\n\n"
                "📌 Pročitaj pravila i uživaj na serveru!"
            ),
            color=0x00C853,
            timestamp=discord.utils.utcnow()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"Ukupno članova: {guild.member_count}")
        await welcome_channel.send(embed=embed)

    log = await get_log_channel(guild)
    if not log:
        return
    embed_log = discord.Embed(
        title="✅ Novi član se pridružio",
        color=0x00C853,
        timestamp=discord.utils.utcnow()
    )
    embed_log.add_field(name="👤 Korisnik", value=f"{member.mention} (`{member}`)", inline=True)
    embed_log.add_field(name="🆔 ID", value=member.id, inline=True)
    if inviter:
        embed_log.add_field(name="📨 Pozvao", value=f"{inviter.mention} (`{inviter}`)", inline=True)
    embed_log.set_thumbnail(url=member.display_avatar.url)
    embed_log.set_footer(text=f"Ukupno članova: {guild.member_count}")
    await log.send(embed=embed_log)


@bot.event
async def on_member_remove(member: discord.Member):
    log = await get_log_channel(member.guild)
    if not log:
        return
    embed = discord.Embed(
        title="🚪 Član napustio server",
        color=0x808080,
        timestamp=discord.utils.utcnow()
    )
    embed.add_field(name="👤 Korisnik", value=f"`{member}`", inline=True)
    embed.add_field(name="🆔 ID", value=member.id, inline=True)
    roles = [r.mention for r in member.roles if r.name != "@everyone"]
    embed.add_field(name="🎭 Rolovi", value=", ".join(roles) if roles else "*bez rolova*", inline=False)
    embed.set_thumbnail(url=member.display_avatar.url)
    await log.send(embed=embed)


@bot.event
async def on_member_ban(guild: discord.Guild, user: discord.User):
    log = await get_log_channel(guild)
    if not log:
        return
    embed = discord.Embed(
        title="⛔ Član banovan",
        color=0xFF0000,
        timestamp=discord.utils.utcnow()
    )
    embed.add_field(name="👤 Korisnik", value=f"{user.mention} (`{user}`)", inline=True)
    embed.add_field(name="🆔 ID", value=user.id, inline=True)
    embed.set_thumbnail(url=user.display_avatar.url)
    await log.send(embed=embed)


@bot.event
async def on_member_unban(guild: discord.Guild, user: discord.User):
    log = await get_log_channel(guild)
    if not log:
        return
    embed = discord.Embed(
        title="✅ Član odbanovan",
        color=0x00C853,
        timestamp=discord.utils.utcnow()
    )
    embed.add_field(name="👤 Korisnik", value=f"{user.mention} (`{user}`)", inline=True)
    embed.add_field(name="🆔 ID", value=user.id, inline=True)
    embed.set_thumbnail(url=user.display_avatar.url)
    await log.send(embed=embed)


@bot.event
async def on_member_update(before: discord.Member, after: discord.Member):
    log = await get_log_channel(before.guild)
    if not log:
        return

    if before.nick != after.nick:
        embed = discord.Embed(
            title="✏️ Nickname promenjen",
            color=0x3498DB,
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="👤 Korisnik", value=f"{after.mention} (`{after}`)", inline=True)
        embed.add_field(name="📝 Pre", value=before.nick or "*bez nicka*", inline=True)
        embed.add_field(name="📝 Nakon", value=after.nick or "*bez nicka*", inline=True)
        embed.set_footer(text=f"ID: {after.id}")
        await log.send(embed=embed)

    added_roles = set(after.roles) - set(before.roles)
    removed_roles = set(before.roles) - set(after.roles)

    if added_roles:
        embed = discord.Embed(
            title="🎭 Rol dodat",
            color=0x00C853,
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="👤 Korisnik", value=f"{after.mention} (`{after}`)", inline=True)
        embed.add_field(name="➕ Dodat rol", value=", ".join(r.mention for r in added_roles), inline=True)
        embed.set_footer(text=f"ID: {after.id}")
        await log.send(embed=embed)

    if removed_roles:
        embed = discord.Embed(
            title="🎭 Rol uklonjen",
            color=0xFF4444,
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="👤 Korisnik", value=f"{after.mention} (`{after}`)", inline=True)
        embed.add_field(name="➖ Uklonjen rol", value=", ".join(r.mention for r in removed_roles), inline=True)
        embed.set_footer(text=f"ID: {after.id}")
        await log.send(embed=embed)


@bot.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    log = await get_log_channel(member.guild)
    if not log:
        return

    if before.channel is None and after.channel is not None:
        embed = discord.Embed(
            title="🔊 Ušao u voice kanal",
            color=0x00C853,
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="👤 Korisnik", value=f"{member.mention} (`{member}`)", inline=True)
        embed.add_field(name="🔊 Kanal", value=after.channel.name, inline=True)
        await log.send(embed=embed)

    elif before.channel is not None and after.channel is None:
        embed = discord.Embed(
            title="🔇 Izašao iz voice kanala",
            color=0xFF4444,
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="👤 Korisnik", value=f"{member.mention} (`{member}`)", inline=True)
        embed.add_field(name="🔊 Kanal", value=before.channel.name, inline=True)
        await log.send(embed=embed)

    elif before.channel != after.channel:
        embed = discord.Embed(
            title="🔀 Promenio voice kanal",
            color=0xFFA500,
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="👤 Korisnik", value=f"{member.mention} (`{member}`)", inline=True)
        embed.add_field(name="⬅️ Pre", value=before.channel.name, inline=True)
        embed.add_field(name="➡️ Nakon", value=after.channel.name, inline=True)
        await log.send(embed=embed)




# === /admin komande (mute / unmute) ===
from datetime import timedelta as _td_admin

admin_group = app_commands.Group(name="admin", description="Staff admin komande")


@admin_group.command(name="mute", description="Mutuj korisnika na određeno vreme")
@app_commands.describe(
    member="Korisnik kojeg mutujes",
    minutes="Trajanje mute-a u minutima",
    razlog="Razlog mute-a"
)
async def admin_mute(interaction: discord.Interaction, member: discord.Member, minutes: int, razlog: str):
    if not has_staff_role(interaction.user):
        await interaction.response.send_message("🚫 Samo Staff može koristiti ovu komandu.", ephemeral=True)
        return

    try:
        await member.timeout(_td_admin(minutes=minutes), reason=razlog)
    except discord.Forbidden:
        await interaction.response.send_message("❌ Nemam permisije da mutujem ovog korisnika.", ephemeral=True)
        return
    except Exception as e:
        await interaction.response.send_message(f"❌ Greška: {e}", ephemeral=True)
        return

    embed = discord.Embed(
        title="🔇 Mutovan si",
        description=(
            f"Mutovan si na serveru **{interaction.guild.name}**.\n\n"
            f"⏱️ **Trajanje:** {minutes} minuta\n"
            f"📌 **Razlog:** {razlog}\n"
            f"👮 **Staff:** {interaction.user.name}"
        ),
        color=0xff4444
    )
    embed.set_footer(text="Velter Roleplay • Staff tim")
    if interaction.guild.icon:
        embed.set_thumbnail(url=interaction.guild.icon.url)

    dm_status = "✅ DM poslat"
    try:
        await member.send(embed=embed)
    except:
        dm_status = "⚠️ DM nije mogao biti poslat"

    await interaction.response.send_message(
        f"✅ {member.mention} mutovan na **{minutes} min**.\n📌 Razlog: {razlog}\n{dm_status}",
        ephemeral=True
    )


@admin_group.command(name="unmute", description="Skini mute korisniku")
@app_commands.describe(member="Korisnik kojem skidaš mute")
async def admin_unmute(interaction: discord.Interaction, member: discord.Member):
    if not has_staff_role(interaction.user):
        await interaction.response.send_message("🚫 Samo Staff može koristiti ovu komandu.", ephemeral=True)
        return

    try:
        await member.timeout(None, reason=f"Unmute od {interaction.user}")
    except discord.Forbidden:
        await interaction.response.send_message("❌ Nemam permisije.", ephemeral=True)
        return

    try:
        await member.send(f"🔊 Skinut ti je mute na serveru **{interaction.guild.name}**.")
    except:
        pass

    await interaction.response.send_message(f"✅ {member.mention} više nije mutovan.", ephemeral=True)


cc_group = app_commands.Group(name="cc", description="Clear chat komande", parent=admin_group)


@cc_group.command(name="clear", description="Obriši kompletan chat (klonira kanal)")
async def admin_cc_clear(interaction: discord.Interaction):
    if not has_staff_role(interaction.user):
        await interaction.response.send_message("🚫 Nemaš dozvolu za ovu komandu.", ephemeral=True)
        return

    channel = interaction.channel
    if not isinstance(channel, discord.TextChannel):
        await interaction.response.send_message("❌ Ova komanda radi samo u tekstualnim kanalima.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True, thinking=True)

    try:
        position = channel.position
        new_channel = await channel.clone(reason=f"Chat clear by {interaction.user}")
        await new_channel.edit(position=position)
        await channel.delete(reason=f"Chat clear by {interaction.user}")
        await new_channel.send("🧹 Chat je očišćen.")
    except discord.Forbidden:
        await interaction.followup.send("❌ Nemam dozvolu (treba mi Manage Channels).", ephemeral=True)
    except discord.HTTPException as e:
        await interaction.followup.send(f"❌ Greška: {e}", ephemeral=True)


bot.tree.add_command(admin_group)
# === kraj /admin komandi ===


if __name__ == "__main__":
    if not TOKEN:
        print("GREŠKA: DISCORD_TOKEN nije postavljen!")
        exit(1)
    bot.run(TOKEN)
