import json
import hashlib
import re
import datetime
from mcrcon import MCRcon

def format_date_ledger(dt_val, fmt="dd-mm-yy"):
    if not dt_val or dt_val == "N/A":
        return "N/A"
    
    dt_obj = None
    if isinstance(dt_val, (int, float)):
        try:
            if dt_val > 1e11: # milliseconds
                dt_obj = datetime.datetime.fromtimestamp(dt_val / 1000.0)
            else:
                dt_obj = datetime.datetime.fromtimestamp(dt_val)
        except:
            pass
    elif isinstance(dt_val, str):
        dt_val = dt_val.strip()
        if dt_val.isdigit():
            try:
                val = float(dt_val)
                if val > 1e11:
                    dt_obj = datetime.datetime.fromtimestamp(val / 1000.0)
                else:
                    dt_obj = datetime.datetime.fromtimestamp(val)
            except:
                pass
        else:
            m = re.match(r'^(\d{4})-(\d{2})-(\d{2})$', dt_val[:10])
            if m:
                try:
                    dt_obj = datetime.datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                except:
                    pass
            else:
                m = re.match(r'^(\d{2})-(\d{2})-(\d{2,4})$', dt_val)
                if m:
                    day, month, year_str = int(m.group(1)), int(m.group(2)), m.group(3)
                    year = 2000 + int(year_str) if len(year_str) == 2 else int(year_str)
                    try:
                        dt_obj = datetime.datetime(year, month, day)
                    except:
                        pass
                else:
                    if 'T' in dt_val:
                        try:
                            date_part = dt_val.split('T')[0]
                            m = re.match(r'^(\d{4})-(\d{2})-(\d{2})$', date_part)
                            if m:
                                dt_obj = datetime.datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                        except:
                            pass

    if dt_obj:
        if fmt == "dd-mm-yy":
            return dt_obj.strftime("%d-%m-%y")
        elif fmt == "dd-mm":
            return dt_obj.strftime("%d-%m")
            
    if isinstance(dt_val, str) and '-' in dt_val:
        parts = dt_val.split('-')
        if len(parts) == 3:
            if len(parts[0]) == 4: # YYYY-MM-DD
                dd, mm, yy = parts[2], parts[1], parts[0][2:]
            else: # DD-MM-YYYY or DD-MM-YY
                dd, mm, yy = parts[0], parts[1], parts[2][-2:]
            if fmt == "dd-mm-yy":
                return f"{dd}-{mm}-{yy}"
            elif fmt == "dd-mm":
                return f"{dd}-{mm}"
                
    return str(dt_val)

# ── Lane registry ─────────────────────────────────────────────────────────────
LANE_MAP = {
    0: "ATTENDANCE_IN",
    1: "ATTENDANCE_OUT",
    2: "SITE_REGISTRATION",
    3: "CONTRACT_AWARD",
    4: "CLAIM_SUBMISSION",
    5: "CLAIM_RESOLUTION",
    6: "PAYMENT_TRANSACTION",
    7: "EOD_SIGNOFF"
}

# ── Sector colour palette ─────────────────────────────────────────────────────
SECTOR_COLOR = {
    "north": "lime",
    "south": "yellow",
    "east":  "red",
    "west":  "light_blue"
}

# ── Y layer constants ─────────────────────────────────────────────────────────
#
#   Y=-60  grass_block  ← actual ground surface
#   Y=-59  player walk level (spawn platform surface / runway walk glass)
#   Y=-58  ledge stained-glass (one block higher than runway, side strips)
#   Y=-57  chain + shulker level (blockchain sits here, on top of ledge glass)
#
Y_GROUND  = -60   # grass
Y_WALK    = -59   # runway stained-glass / spawn platform
Y_LEDGE   = -58   # side ledge stained-glass
Y_CHAIN   = -57   # chain & shulker

# ── Geometry ──────────────────────────────────────────────────────────────────
#   Plaza: X/Z = -2..+2  (5×5, centre at 0,0)
#   Gateway gap: 3 blocks reserved outside plaza edge before chain starts
#   Chain/shulker strip starts at offset=3 from origin
#     e.g. North left strip: X=-2, Z starts at -3, goes to -102
#
CHAIN_START = 3     # distance from origin to first chain/shulker block
CHAIN_LEN   = 100   # runway length in blocks


class MinecraftLedger:
    def __init__(self,
                 host="127.0.0.1",
                 port=25575,
                 password="rojgaar_secret_2025",
                 world_seed="rojgaar_default_seed"):
        self.host       = host
        self.port       = port
        self.password   = password
        self.world_seed = world_seed
        self.rcon       = None

    # ── RCON connection ───────────────────────────────────────────────────────
    def connect(self):
        try:
            self.rcon = MCRcon(self.host, self.password, port=self.port)
            self.rcon.connect()
            return True
        except Exception as e:
            print(f"[Ledger Error] RCON connect failed: {e}")
            return False

    def disconnect(self):
        if self.rcon:
            self.rcon.disconnect()
            self.rcon = None

    def send_cmd(self, cmd):
        if not self.rcon:
            raise ConnectionError("RCON not connected.")
        return self.rcon.command(cmd)

    # ── Coordinate helpers ────────────────────────────────────────────────────
    def get_coords_for_seq(self, zone, seq):
        """
        Return (x, y, z) for the shulker/chain block at sequence index `seq`.

        Layout cross-section (North sector, top-down):

          X:  -2          -1    0   +1          +2
         Y=-57 [SHK/CHN]                    [SHK/CHN]  ← chain level
         Y=-58 [lime_gl]                    [lime_gl]  ← ledge glass
         Y=-59            [lime][lime][lime]            ← walkway glass
         Y=-60 [sea_lnt]  [sl]  [sl]  [sl]  [sea_lnt]  ← sea lanterns

        North/South sectors run along Z axis, strips at X=±2.
        East/West  sectors run along X axis, strips at Z=±2.

        Alternating pattern along each strip:
          pillar(±2) → chain(3) → shulker(4) → chain(5) → shulker(6) → ...
          offset = CHAIN_START + 1 + (seq * 2)

        Zone 0 ATTENDANCE_IN       → North left  X=-2, Y=-57, Z=-(off)
        Zone 1 ATTENDANCE_OUT      → North right X=+2, Y=-57, Z=-(off)
        Zone 2 SITE_REGISTRATION   → South left  X=-2, Y=-57, Z=+(off)
        Zone 3 CONTRACT_AWARD      → South right X=+2, Y=-57, Z=+(off)
        Zone 4 CLAIM_SUBMISSION    → East  left  Z=-2, Y=-57, X=+(off)
        Zone 5 CLAIM_RESOLUTION    → East  right Z=+2, Y=-57, X=+(off)
        Zone 6 PAYMENT_TRANSACTION → West  left  Z=-2, Y=-57, X=-(off)
        Zone 7 PAYMENT_SIGNOFF     → West  right Z=+2, Y=-57, X=-(off)
        """
        # +1 skips the first chain slot right after the plaza pillar,
        # *2 leaves a chain gap between each shulker.
        off = CHAIN_START + 1 + (seq * 2)
        y   = Y_CHAIN
        if   zone == 0: return -2,  y, -off
        elif zone == 1: return  2,  y, -off
        elif zone == 2: return -2,  y,  off
        elif zone == 3: return  2,  y,  off
        elif zone == 4: return  off, y, -2
        elif zone == 5: return  off, y,  2
        elif zone == 6: return -off, y, -2
        elif zone == 7: return -off, y,  2
        else: raise ValueError(f"Invalid zone: {zone}")

    def _sector_of_zone(self, zone):
        if zone in [0, 1]: return "north"
        if zone in [2, 3]: return "south"
        if zone in [4, 5]: return "east"
        return "west"

    def _color_of_zone(self, zone):
        return SECTOR_COLOR[self._sector_of_zone(zone)]

    def _shulker_facing(self, zone):
        """
        Shulker opens horizontally INWARD toward the walkway centre.
        North/South: strips at X=±2, walkway at X=0.
          X=-2 (left)  → face east  (+X, toward centre)
          X=+2 (right) → face west  (-X, toward centre)
        East/West: strips at Z=±2, walkway at Z=0.
          Z=-2 (left)  → face south (+Z, toward centre)
          Z=+2 (right) → face north (-Z, toward centre)
        """
        if   zone == 0: return "east"
        elif zone == 1: return "west"
        elif zone == 2: return "east"
        elif zone == 3: return "west"
        elif zone == 4: return "south"
        elif zone == 5: return "north"
        elif zone == 6: return "south"
        elif zone == 7: return "north"

    def _chain_axis(self, zone):
        # North/South chains run along Z; East/West along X
        return "z" if zone in [0, 1, 2, 3] else "x"

    def _sign_facing(self, zone):
        # Sign faces same direction as shulker opening (inward)
        return self._shulker_facing(zone)

    def _sign_coords(self, zone, sx, sy, sz):
        """
        Wall signs attach to the face of a solid block.
        Sign is placed ONE BLOCK INWARD from the ledge glass (Y=-58),
        attaching to the ledge glass face that faces the walkway.

        The sign setblock coord is the AIR position adjacent to the ledge glass,
        on the walkway side. The sign's facing= points toward the walkway (inward).

        Ledge glass is at (sx, Y_LEDGE, sz).
        Inward direction per zone:
          zone 0,2 (X=-2, faces east):  sign at X=-1, same Z
          zone 1,3 (X=+2, faces west):  sign at X=+1, same Z
          zone 4,6 (Z=-2, faces south): sign at Z=-1, same X
          zone 5,7 (Z=+2, faces north): sign at Z=+1, same X
        """
        if   zone in [0, 2]: return sx + 1, Y_LEDGE, sz   # X=-2 ledge, sign at X=-1
        elif zone in [1, 3]: return sx - 1, Y_LEDGE, sz   # X=+2 ledge, sign at X=+1
        elif zone in [4, 6]: return sx,     Y_LEDGE, sz + 1  # Z=-2 ledge, sign at Z=-1
        elif zone in [5, 7]: return sx,     Y_LEDGE, sz - 1  # Z=+2 ledge, sign at Z=+1

    # ── World initialisation ──────────────────────────────────────────────────
    def _setblock_strip(self, fixed_axis, fixed_val, vary_start, vary_end,
                        y, block, axis_is_x=True):
        """
        Place blocks one at a time along a strip.

        fixed_axis  : which axis is held constant ('x' or 'z')
        fixed_val   : the constant coordinate value
        vary_start  : start of the varying coordinate (inclusive)
        vary_end    : end of the varying coordinate (inclusive)
        y           : Y level
        block       : full block string e.g. 'minecraft:chain[axis=z]'
        axis_is_x   : if True, fixed_axis is X and we vary Z;
                      if False, fixed_axis is Z and we vary X.
        """
        step = 1 if vary_end >= vary_start else -1
        for v in range(vary_start, vary_end + step, step):
            if axis_is_x:
                # fixed X, varying Z
                self.send_cmd(f"setblock {fixed_val} {y} {v} {block}")
            else:
                # fixed Z, varying X
                self.send_cmd(f"setblock {v} {y} {fixed_val} {block}")

    def init_world(self):
        """
        Build the complete physical ledger world from scratch.

        Full layer stack per runway cross-section (7 blocks wide):
          Y=-60  sea_lantern  (replaces grass, runs full 7-wide under runway+ledge)
          Y=-59  stained_glass  3-wide centre walkway  (walk surface)
          Y=-58  stained_glass  1-wide ledge strips at X/Z=±2  (raised ledge)
          Y=-57  chain[axis]    skeleton, write_block() replaces with shulkers

        Spawn platform (5×5 polished blackstone) sits at Y=-59 on top of grass.
        World spawn set to 0,-60,0 (the grass block); player appears at Y=-59.

        All blocks are placed one at a time via setblock to avoid Minecraft's
        32768 block fill limit and unloaded-chunk errors.
        """
        print("[Ledger] Initialising world...")
        try:
            # ── Force-load the entire build volume ────────────────────────────
            end = CHAIN_START + CHAIN_LEN  # 103
            self.send_cmd(f"forceload add -{end} -{end} {end} {end}")

            # ── World rules ──────────────────────────────────────────────────
            self.send_cmd("time set day")
            self.send_cmd("gamerule doDaylightCycle false")
            self.send_cmd("gamerule doMobSpawning false")
            self.send_cmd("gamerule spawnRadius 0")
            self.send_cmd("gamerule defaultGameMode adventure")
            self.send_cmd("kill @e[type=!player]")

            # ── Clear above-ground in manageable chunks (Y=-59 up) ───────────
            # Use quadrant fills to stay under 32768 block limit.
            # Each quadrant: ~103 × ~103 × 6 = ~63,654 → split Y too.
            for y_lo, y_hi in [(-59, -57), (-56, -54)]:
                self.send_cmd(f"fill -{end} {y_lo} -{end} 0 {y_hi} 0 air")
                self.send_cmd(f"fill 1 {y_lo} -{end} {end} {y_hi} 0 air")
                self.send_cmd(f"fill -{end} {y_lo} 1 0 {y_hi} {end} air")
                self.send_cmd(f"fill 1 {y_lo} 1 {end} {y_hi} {end} air")

            # ── 1. Spawn plaza (5×5 polished blackstone at Y=-59) ─────────────
            for px in range(-2, 3):
                for pz in range(-2, 3):
                    self.send_cmd(
                        f"setblock {px} {Y_WALK} {pz} minecraft:polished_blackstone"
                    )
            self.send_cmd(f"setblock 0 {Y_WALK} 0 minecraft:target")

            # ── 2. Corner pillars (crying obsidian, 3 tall Y=-59..-57) ────────
            for cx, cz in [(-2, -2), (2, -2), (2, 2), (-2, 2)]:
                for py in range(Y_WALK, Y_CHAIN + 1):  # -59, -58, -57
                    self.send_cmd(
                        f"setblock {cx} {py} {cz} minecraft:crying_obsidian"
                    )



            # ── 3–6. Build each runway strip block by block ───────────────────
            # For each offset position along the runway (3..102):
            for i in range(CHAIN_LEN):  # 0..99
                off = CHAIN_START + i   # 3..102

                # ── NORTH (Z negative) ───────────────────────────────────────
                z_n = -off
                for x_sl in range(-2, 3):  # X=-2..+2 → sea lanterns at Y=-60
                    self.send_cmd(f"setblock {x_sl} {Y_GROUND} {z_n} minecraft:sea_lantern")
                for x_wk in range(-1, 2):  # X=-1..+1 → walkway glass at Y=-59
                    self.send_cmd(f"setblock {x_wk} {Y_WALK} {z_n} minecraft:lime_stained_glass")
                # Ledge glass at X=±2, Y=-58
                self.send_cmd(f"setblock -2 {Y_LEDGE} {z_n} minecraft:lime_stained_glass")
                self.send_cmd(f"setblock  2 {Y_LEDGE} {z_n} minecraft:lime_stained_glass")
                # Chain skeleton at X=±2, Y=-57
                self.send_cmd(f"setblock -2 {Y_CHAIN} {z_n} minecraft:chain[axis=z]")
                self.send_cmd(f"setblock  2 {Y_CHAIN} {z_n} minecraft:chain[axis=z]")
                if off == 3:
                    # Chests sit ON TOP of the first chain (Y=-56)
                    self.send_cmd(f"setblock -2 {Y_CHAIN+1} {z_n} minecraft:chest[facing=south]")
                    self.send_cmd(f"setblock  2 {Y_CHAIN+1} {z_n} minecraft:chest[facing=south]")

                # ── SOUTH (Z positive) ───────────────────────────────────────
                z_s = off
                for x_sl in range(-2, 3):
                    self.send_cmd(f"setblock {x_sl} {Y_GROUND} {z_s} minecraft:sea_lantern")
                for x_wk in range(-1, 2):
                    self.send_cmd(f"setblock {x_wk} {Y_WALK} {z_s} minecraft:yellow_stained_glass")
                self.send_cmd(f"setblock -2 {Y_LEDGE} {z_s} minecraft:yellow_stained_glass")
                self.send_cmd(f"setblock  2 {Y_LEDGE} {z_s} minecraft:yellow_stained_glass")
                self.send_cmd(f"setblock -2 {Y_CHAIN} {z_s} minecraft:chain[axis=z]")
                self.send_cmd(f"setblock  2 {Y_CHAIN} {z_s} minecraft:chain[axis=z]")
                if off == 3:
                    self.send_cmd(f"setblock -2 {Y_CHAIN+1} {z_s} minecraft:chest[facing=north]")
                    self.send_cmd(f"setblock  2 {Y_CHAIN+1} {z_s} minecraft:chest[facing=north]")

                # ── EAST (X positive) ────────────────────────────────────────
                x_e = off
                for z_sl in range(-2, 3):
                    self.send_cmd(f"setblock {x_e} {Y_GROUND} {z_sl} minecraft:sea_lantern")
                for z_wk in range(-1, 2):
                    self.send_cmd(f"setblock {x_e} {Y_WALK} {z_wk} minecraft:red_stained_glass")
                self.send_cmd(f"setblock {x_e} {Y_LEDGE} -2 minecraft:red_stained_glass")
                self.send_cmd(f"setblock {x_e} {Y_LEDGE}  2 minecraft:red_stained_glass")
                self.send_cmd(f"setblock {x_e} {Y_CHAIN} -2 minecraft:chain[axis=x]")
                self.send_cmd(f"setblock {x_e} {Y_CHAIN}  2 minecraft:chain[axis=x]")
                if off == 3:
                    self.send_cmd(f"setblock {x_e} {Y_CHAIN+1} -2 minecraft:chest[facing=west]")
                    self.send_cmd(f"setblock {x_e} {Y_CHAIN+1}  2 minecraft:chest[facing=west]")

                # ── WEST (X negative) ────────────────────────────────────────
                x_w = -off
                for z_sl in range(-2, 3):
                    self.send_cmd(f"setblock {x_w} {Y_GROUND} {z_sl} minecraft:sea_lantern")
                for z_wk in range(-1, 2):
                    self.send_cmd(f"setblock {x_w} {Y_WALK} {z_wk} minecraft:light_blue_stained_glass")
                self.send_cmd(f"setblock {x_w} {Y_LEDGE} -2 minecraft:light_blue_stained_glass")
                self.send_cmd(f"setblock {x_w} {Y_LEDGE}  2 minecraft:light_blue_stained_glass")
                self.send_cmd(f"setblock {x_w} {Y_CHAIN} -2 minecraft:chain[axis=x]")
                self.send_cmd(f"setblock {x_w} {Y_CHAIN}  2 minecraft:chain[axis=x]")
                if off == 3:
                    self.send_cmd(f"setblock {x_w} {Y_CHAIN+1} -2 minecraft:chest[facing=east]")
                    self.send_cmd(f"setblock {x_w} {Y_CHAIN+1}  2 minecraft:chest[facing=east]")

                if (i + 1) % 25 == 0:
                    print(f"[Ledger]   ...placed {i + 1}/{CHAIN_LEN} positions")

            # Sector label signs removed per user request for personal build customization

            # ── 8. World spawn ────────────────────────────────────────────────
            # setworldspawn takes the block the player spawns ON.
            self.send_cmd("setworldspawn 0 -58 0")
            self.send_cmd("gamemode adventure @a")

            print("[Ledger] World initialised successfully.")
            return True

        except Exception as e:
            print(f"[Ledger Error] init_world failed: {e}")
            return False

    # ── Hashing ───────────────────────────────────────────────────────────────
    def calculate_hash(self, x, y, z, prev_hash, record_json):
        canonical = json.dumps(record_json, sort_keys=True, separators=(',', ':'))
        preimage  = f"{self.world_seed}|{x}|{y}|{z}|{prev_hash}|{canonical}"
        return hashlib.sha256(preimage.encode('utf-8')).hexdigest()

    # ── NBT / block string helpers ────────────────────────────────────────────
    def _shulker_block_id(self, zone):
        return f"minecraft:{self._color_of_zone(zone)}_shulker_box"

    def _build_sign_nbt(self, zone, seq, record_dict):
        """Build 4-line sign NBT string. Sign is a wall sign facing inward."""
        rec_type  = record_dict.get("type", "")
        dt        = format_date_ledger(record_dict.get("dt", "N/A"), "dd-mm")

        # Setup custom abbreviations for headers
        if zone == 0:
            hdr = "ATTEND_IN"
        elif zone == 1:
            hdr = "ATTEND_OUT"
        elif zone == 2:
            hdr = "SITE_REG"
        elif zone == 3:
            hdr = "CON_AWARD"
        elif zone == 4:
            hdr = "CLAIM_SUB"
        elif zone == 5:
            hdr = "CLAIM_RES"
        elif zone == 6:
            hdr = "PAYMENT"
        else:
            hdr = "PAY_SIGNOFF"

        label = f"{hdr}-{seq}"
        
        l4_json_override = None

        if zone in [0, 1]:
            l2 = record_dict.get("wrk", "WRK")[:15]
            if zone == 0:
                l3 = record_dict.get("status",  "CHECKED IN")[:15]
            else:
                l3 = f"{record_dict.get('hours','8')} HOURS"[:15]
            l4 = f"{record_dict.get('sid','SID')[:8]} {dt[:5]}"[:15]
            tc, l3c = "dark_green", "dark_aqua"
        elif zone == 2: # SITE_REG
            l2 = record_dict.get("emp",  "EMP")[:15]
            l3 = "REGISTERED"
            l4_sid = record_dict.get("sid", "SID")[:8]
            l4_json_override = f'[{{"text":"{l4_sid} ","color":"dark_aqua"}},{{"text":"{dt[:5]}","color":"black"}}]'
            tc, l3c = "gold", "black"
        elif zone == 3: # CONTRACT_AWARD
            l2 = record_dict.get("emp",  "EMP")[:15]
            l3 = "AWARDED TO"
            l4_con = record_dict.get("con", "CON")[:8]
            l4_json_override = f'[{{"text":"{l4_con} ","color":"dark_aqua"}},{{"text":"{dt[:5]}","color":"black"}}]'
            tc, l3c = "gold", "dark_blue"
        elif zone in [4, 5]:
            if rec_type == "claim":
                l2 = record_dict.get("wrk",    "WRK"    )[:15]
                l3 = record_dict.get("status", "PENDING")[:15]
                l4 = f"{record_dict.get('con','CON')[:8]} {dt[:5]}"[:15]
            else:
                l2 = record_dict.get("claim_id", "CLAIM"   )[:15]
                l3 = record_dict.get("action",   "RESPONSE")[:15]
                l4 = f"{record_dict.get('resp_by','RESP')[:8]} {dt[:5]}"[:15]
            tc  = "dark_red"
            l3c = "yellow" if rec_type == "claim" else "dark_green"
        else:  # 6, 7
            if rec_type == "payment":
                l2 = record_dict.get("wrk", "WRK")[:15]
                l3 = "CONFIRMED PAID"
                l4 = f"{record_dict.get('sid', 'SID')[:8]} {dt[:5]}"[:15]
            else:
                l2 = record_dict.get("con", "CON")[:15]
                l3 = "EOD SIGN-OFF"
                l4 = f"{record_dict.get('sid', 'SID')[:8]} {dt[:5]}"[:15]
            tc  = "dark_blue"
            l3c = "dark_green"

        m1 = f'{{"text":"{label}","color":"{tc}","bold":true}}'
        m2 = f'{{"text":"{l2}","color":"black"}}'
        m3 = f'{{"text":"{l3}","color":"{l3c}","bold":true}}'
        if l4_json_override:
            m4 = l4_json_override
        else:
            m4 = f'{{"text":"{l4}","color":"black"}}'

        facing = self._sign_facing(zone)
        # Full block string including blockstate and NBT
        return (
            f"minecraft:bamboo_wall_sign[facing={facing}]"
            f"{{front_text:{{messages:['{m1}','{m2}','{m3}','{m4}']}}}}"
        )

    # ── Book data helpers ─────────────────────────────────────────────────────
    def get_block_data(self, zone, seq):
        """Read the written book from the shulker at (zone, seq) and return parsed dict."""
        x, y, z  = self.get_coords_for_seq(zone, seq)
        response = self.send_cmd(f"data get block {x} {y} {z} Items[0]")

        if ("has no element" in response
                or "is not a container" in response
                or "id:" not in response):
            return None

        try:
            # Locate pages array in SNBT output
            start = response.find("pages: ['")
            if start == -1:
                start = response.find('pages: ["')
                if start == -1:
                    return None
                end = response.find('"]', start)
                raw = response[start + 9:end]
            else:
                end = response.find("']", start)
                raw = response[start + 9:end]

            raw = raw.replace('\\\\', '\\')
            return json.loads(json.loads(raw))
        except Exception as e:
            print(f"[Ledger Error] parse failed at ({x},{y},{z}): {e}")
            return None

    def get_latest_seq_and_hash(self, zone):
        """Scan the lane to find the next free sequence index and last block hash."""
        seq       = 0
        last_hash = "0" * 64

        while True:
            x, y, z  = self.get_coords_for_seq(zone, seq)
            response = self.send_cmd(f"data get block {x} {y} {z}")

            # A shulker with data will contain "Items" in its NBT output
            if ("has no element" in response
                    or "is not a container" in response
                    or "Items" not in response):
                break

            bd = self.get_block_data(zone, seq)
            if bd and "block_hash" in bd:
                last_hash = bd["block_hash"]
                seq += 1
            else:
                break

        return seq, last_hash

    # ── Core write ────────────────────────────────────────────────────────────
    def write_block(self, zone, record_dict):
        """
        Write a new transaction record to the ledger.

        Steps:
          1. Find next seq and prev_hash by scanning the lane.
          2. Compute block hash and embed in record.
          3. Replace the skeleton chain block at this seq with a coloured shulker
             (facing inward, horizontal open — NOT up).
          4. Insert written book into shulker slot 0.
          5. Place wall sign on the inward face of the ledge glass (Y=-58) directly
             below the shulker, attaching it to that glass block's face.
        """
        if zone not in LANE_MAP:
            raise ValueError(f"Invalid zone {zone}")

        try:
            seq, prev_hash = self.get_latest_seq_and_hash(zone)
            x, y, z        = self.get_coords_for_seq(zone, seq)   # Y=-57
            axis           = self._chain_axis(zone)
            shulker_facing = self._shulker_facing(zone)
            shulker_id     = self._shulker_block_id(zone)

            # Hash record
            record_dict["prev_hash"]  = prev_hash
            block_hash                = self.calculate_hash(x, y, z, prev_hash, record_dict)
            record_dict["block_hash"] = block_hash

            # Ensure ledge glass exists directly below shulker (Y=-58, same X,Z)
            color = self._color_of_zone(zone)
            self.send_cmd(
                f"setblock {x} {Y_LEDGE} {z} "
                f"minecraft:{color}_stained_glass keep"
            )

            # Place shulker at Y=-57 with correct horizontal facing
            # Using 'destroy' mode to fully remove old block before placing
            # shulker with the correct facing blockstate (avoids defaulting to 'up')
            res_shulker = self.send_cmd(
                f"setblock {x} {y} {z} "
                f"{shulker_id}[facing={shulker_facing}] destroy"
            )

            # Place chain at next seq position to maintain pattern (keep = don't overwrite if exists)
            nx, ny, nz = self.get_coords_for_seq(zone, seq + 1)
            self.send_cmd(
                f"setblock {nx} {ny} {nz} minecraft:chain[axis={axis}] keep"
            )

            # Write book into shulker (slot 0)
            canonical  = json.dumps(record_dict, sort_keys=True, separators=(',', ':'))
            escaped    = canonical.replace('"', '\\\\"')
            page_json  = f'"{escaped}"'
            book_title = f"{LANE_MAP[zone]}_{seq}"
            book_nbt   = (
                f'{{Items:[{{Slot:0b,id:"minecraft:written_book",Count:1b,'
                f'tag:{{title:"{book_title}",author:"RojgaarBot",'
                f'pages:[\'{page_json}\']}}}}]}}'
            )
            res_book = self.send_cmd(f"data merge block {x} {y} {z} {book_nbt}")

            # Place wall sign on inward face of the ledge glass block (Y=-58)
            # Sign is placed at the air position one block inward from the ledge,
            # with facing= pointing inward so it attaches to the glass face.
            sign_block = self._build_sign_nbt(zone, seq, record_dict)
            sx, sy, sz = self._sign_coords(zone, x, y, z)
            res_sign   = self.send_cmd(f"setblock {sx} {sy} {sz} {sign_block}")

            # Wipe any dropped item entities instantly
            self.send_cmd("kill @e[type=item,distance=..150]")

            print(
                f"[Ledger] {LANE_MAP[zone]}-{seq} @ ({x},{y},{z}) | "
                f"Shulker:{res_shulker} | Book:{res_book} | Sign:{res_sign} | "
                f"Hash:{block_hash[:12]}..."
            )
            return {
                "block_id": f"{LANE_MAP[zone]}-{seq}",
                "seq": seq,
                "x": x, "y": y, "z": z,
                "hash": block_hash,
                "res_sign": res_sign
            }

        except Exception as e:
            print(f"[Ledger Error] write_block failed: {e}")
            return None

    # ── Verification ──────────────────────────────────────────────────────────
    def verify_block(self, zone, seq):
        x, y, z = self.get_coords_for_seq(zone, seq)
        record  = self.get_block_data(zone, seq)

        if not record:
            return {"status": "MISSING", "error": "No data at coordinates."}

        stored_hash = record.get("block_hash")
        prev_hash   = record.get("prev_hash")

        if not stored_hash or prev_hash is None:
            return {"status": "CORRUPTED", "error": "Hashes missing in book."}

        validation = {k: v for k, v in record.items() if k != "block_hash"}
        recomputed = self.calculate_hash(x, y, z, prev_hash, validation)

        if recomputed == stored_hash:
            return {
                "status":    "VALID",
                "x": x, "y": y, "z": z,
                "hash":      stored_hash,
                "prev_hash": prev_hash,
                "data":      record
            }
        return {
            "status":          "TAMPERED",
            "error":           "Hash mismatch — data altered.",
            "stored_hash":     stored_hash,
            "recomputed_hash": recomputed
        }

    def verify_chain(self, zone):
        print(f"[Ledger] Verifying {LANE_MAP[zone]}...")
        # To handle mid-chain tamper, we must not rely solely on get_latest_seq_and_hash,
        # which stops at the first invalid/missing block.
        # Instead, we scan forward. We know a block was written if there is a shulker block there,
        # or if we successfully find any sequential blocks.
        # Let's count how many total shulker blocks exist in the sequence before hitting a chain block.
        seq = 0
        while True:
            x, y, z = self.get_coords_for_seq(zone, seq)
            response = self.send_cmd(f"data get block {x} {y} {z}")
            # If the block at the coords is not a shulker box of the correct type/color,
            # or if it has no items (or is a chain block), we stop checking.
            # Shulkers are named: minecraft:{color}_shulker_box
            expected_shulker = self._shulker_block_id(zone)
            if expected_shulker not in response and "shulker_box" not in response:
                break
            seq += 1

        if seq == 0:
            print(f"[Ledger] {LANE_MAP[zone]} is empty (Genesis).")
            return True, 0

        expected = "0" * 64
        for i in range(seq):
            result = self.verify_block(zone, i)
            if result["status"] != "VALID":
                print(f"[Audit FAIL] seq={i}: {result.get('error')}")
                return False, i
            if result["prev_hash"] != expected:
                print(f"[Audit FAIL] chain broken at seq={i}: prev_hash mismatch.")
                return False, i
            expected = result["hash"]

        print(f"[Audit OK] {seq} blocks verified. Chain intact.")
        return True, seq

    def verify_all_chains(self):
        print("\n[Ledger] ══ FULL AUDIT ══")
        all_ok = True
        for zone in LANE_MAP:
            ok, count = self.verify_chain(zone)
            flag = "✓ VALID" if ok else "✗ FAILED"
            print(f"  Zone {zone}  {LANE_MAP[zone]:<25}  {flag}  ({count} blocks)")
            if not ok:
                all_ok = False
        print("[Ledger] ══ END AUDIT ══\n")
        return all_ok

    def wipe_state(self):
        """
        Delete all block entries in all 8 zones of the blockchain,
        replacing shulkers with chain skeleton blocks, wiping transaction signs,
        clearing dropped item entities, and leaving all other structures untouched.
        """
        print("[Ledger] Wiping blockchain state...")
        try:
            for zone in LANE_MAP:
                axis = self._chain_axis(zone)
                # We scan/clean up to the runway limit (up to CHAIN_LEN blocks)
                for seq in range(CHAIN_LEN):
                    x, y, z = self.get_coords_for_seq(zone, seq)
                    
                    # Read block data
                    response = self.send_cmd(f"data get block {x} {y} {z}")
                    
                    # If this block is a shulker box (contains 'shulker_box'), we restore chain
                    if "shulker_box" in response.lower() or self._shulker_block_id(zone) in response:
                        # Replace back with chain
                        self.send_cmd(f"setblock {x} {y} {z} minecraft:chain[axis={axis}] destroy")
                        
                        # Find and delete the corresponding sign block
                        sx, sy, sz = self._sign_coords(zone, x, y, z)
                        self.send_cmd(f"setblock {sx} {sy} {sz} minecraft:air destroy")

            # Wipe any dropped item entities instantly
            self.send_cmd("kill @e[type=item,distance=..150]")
            self.send_cmd("setworldspawn 0 -58 0")
            self.send_cmd("tp @a 0 -58 0")
            print("[Ledger] Blockchain state wiped successfully.")
            return True
        except Exception as e:
            print(f"[Ledger Error] wipe_state failed: {e}")
            return False
