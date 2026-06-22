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
    0: "WORKER",
    1: "CONTRACTOR",
    2: "EMPLOYER",
    3: "SITE"
}

# ── Geometry ──────────────────────────────────────────────────────────────────
CENTER_X = -50
CENTER_Z = -50

Y_GROUND = -60
Y_WALK   = -59
Y_LANTERN= -58
Y_SIGN   = -57

CHAIN_START = 3
CHAIN_LEN   = 25

class DatabaseLedger:
    def __init__(self, host="127.0.0.1", port=25575, password="rojgaar_secret_2025"):
        self.host     = host
        self.port     = port
        self.password = password
        self.rcon     = None

    def connect(self):
        try:
            self.rcon = MCRcon(self.host, self.password, port=self.port)
            self.rcon.connect()
            return True
        except Exception as e:
            print(f"[DB Error] RCON connect failed: {e}")
            return False

    def disconnect(self):
        if self.rcon:
            self.rcon.disconnect()
            self.rcon = None

    def send_cmd(self, cmd):
        if not self.rcon:
            raise ConnectionError("RCON not connected.")
        return self.rcon.command(cmd)

    def _get_theme(self, zone):
        if zone == 0:   # Worker (North, -Z)
            return "green_carpet", "stripped_jungle_log", "mossy_cobblestone_wall", "stone_bricks"
        elif zone == 1: # Contractor (South, +Z)
            return "yellow_carpet", "stripped_acacia_log", "sandstone_wall", "stone_bricks"
        elif zone == 2: # Employer (East, +X)
            return "red_carpet", "stripped_oak_log", "red_nether_brick_wall", "stone_bricks"
        elif zone == 3: # Site (West, -X)
            return "blue_carpet", "stripped_birch_log", "diorite_wall", "stone_bricks"

    def _get_coords(self, zone, seq):
        row = seq // 2
        side = seq % 2
        off = 3 + (row * 2)
        
        if zone == 0:
            x = CENTER_X - 2 if side == 0 else CENTER_X + 2
            return x, Y_WALK, CENTER_Z - off
        elif zone == 1:
            x = CENTER_X - 2 if side == 0 else CENTER_X + 2
            return x, Y_WALK, CENTER_Z + off
        elif zone == 2:
            z = CENTER_Z - 2 if side == 0 else CENTER_Z + 2
            return CENTER_X + off, Y_WALK, z
        elif zone == 3:
            z = CENTER_Z - 2 if side == 0 else CENTER_Z + 2
            return CENTER_X - off, Y_WALK, z
        raise ValueError(f"Invalid DB zone {zone}")

    def init_world(self):
        print("[DB Ledger] Initialising Mutable Data Warehouse...")
        try:
            self.send_cmd(f"forceload add {CENTER_X-50} {CENTER_Z-50} {CENTER_X+50} {CENTER_Z+50}")
            
            # Clear airspace
            for y_lo, y_hi in [(-59, -57), (-56, -54)]:
                self.send_cmd(f"fill {CENTER_X-35} {y_lo} {CENTER_Z-35} {CENTER_X+35} {y_hi} {CENTER_Z+35} air")

            # Center Plaza (5x5)
            self.send_cmd(f"fill {CENTER_X-2} {Y_GROUND} {CENTER_Z-2} {CENTER_X+2} {Y_GROUND} {CENTER_Z+2} minecraft:dark_oak_planks")
            for cx, cz in [(-2, -2), (2, -2), (2, 2), (-2, 2)]:
                for py in range(Y_GROUND, Y_LANTERN + 1):
                    self.send_cmd(f"setblock {CENTER_X+cx} {py} {CENTER_Z+cz} minecraft:dark_oak_log")
            
            # Build 4 Sectors
            for zone in range(4):
                carpet, base, wall, enc = self._get_theme(zone)
                
                # Each sector is CHAIN_LEN blocks long (25)
                for i in range(CHAIN_LEN):
                    off = CHAIN_START + i
                    
                    if zone == 0:   # North
                        z = CENTER_Z - off
                        cx, cz, ax, side_l, side_r, sign_f1, sign_f2 = CENTER_X, z, "z", -2, 2, "south", "south"
                        wx_l, wx_r, wz_l, wz_r = -3, 3, 0, 0
                    elif zone == 1: # South
                        z = CENTER_Z + off
                        cx, cz, ax, side_l, side_r, sign_f1, sign_f2 = CENTER_X, z, "z", -2, 2, "north", "north"
                        wx_l, wx_r, wz_l, wz_r = -3, 3, 0, 0
                    elif zone == 2: # East
                        x = CENTER_X + off
                        cx, cz, ax, side_l, side_r, sign_f1, sign_f2 = x, CENTER_Z, "x", -2, 2, "west", "west"
                        wx_l, wx_r, wz_l, wz_r = 0, 0, -3, 3
                    elif zone == 3: # West
                        x = CENTER_X - off
                        cx, cz, ax, side_l, side_r, sign_f1, sign_f2 = x, CENTER_Z, "x", -2, 2, "east", "east"
                        wx_l, wx_r, wz_l, wz_r = 0, 0, -3, 3
                    
                    # 1. Walkway
                    if ax == "z":
                        self.send_cmd(f"fill {cx-1} {Y_GROUND} {cz} {cx+1} {Y_GROUND} {cz} minecraft:dark_oak_planks")
                        self.send_cmd(f"fill {cx-1} {Y_WALK} {cz} {cx+1} {Y_WALK} {cz} minecraft:{carpet}")
                    else:
                        self.send_cmd(f"fill {cx} {Y_GROUND} {cz-1} {cx} {Y_GROUND} {cz+1} minecraft:dark_oak_planks")
                        self.send_cmd(f"fill {cx} {Y_WALK} {cz-1} {cx} {Y_WALK} {cz+1} minecraft:{carpet}")

                    # 2. Enclosures
                    self.send_cmd(f"fill {cx+wx_l} {Y_GROUND} {cz+wz_l} {cx+wx_l} {Y_SIGN} {cz+wz_l} minecraft:{enc}")
                    self.send_cmd(f"fill {cx+wx_r} {Y_GROUND} {cz+wz_r} {cx+wx_r} {Y_SIGN} {cz+wz_r} minecraft:{enc}")

                    # 3. Data Lanes (Lecterns vs Walls)
                    # Every even i is a lectern, every odd i is a wall+lantern
                    if ax == "z":
                        l_x, l_z = cx + side_l, cz
                        r_x, r_z = cx + side_r, cz
                    else:
                        l_x, l_z = cx, cz + side_l
                        r_x, r_z = cx, cz + side_r

                    self.send_cmd(f"setblock {l_x} {Y_GROUND} {l_z} minecraft:{base}")
                    self.send_cmd(f"setblock {r_x} {Y_GROUND} {r_z} minecraft:{base}")

                    if i % 2 == 0:
                        # Lectern
                        fac = "east" if (ax=="z" and side_l==-2) else ("west" if ax=="z" else ("south" if side_l==-2 else "north"))
                        fac2 = "west" if (ax=="z" and side_r==2) else ("east" if ax=="z" else ("north" if side_r==2 else "south"))
                        
                        # Set Lecterns
                        self.send_cmd(f"setblock {l_x} {Y_WALK} {l_z} minecraft:lectern[facing={fac}]")
                        self.send_cmd(f"setblock {r_x} {Y_WALK} {r_z} minecraft:lectern[facing={fac2}]")
                        
                        # Set Blank Signs
                        if zone in [0, 1]:
                            sf1 = "east" if l_x == CENTER_X - 2 else "west"
                            sf2 = "east" if r_x == CENTER_X - 2 else "west"
                        else:
                            sf1 = "south" if l_z == CENTER_Z - 2 else "north"
                            sf2 = "south" if r_z == CENTER_Z - 2 else "north"
                        self.send_cmd(f"setblock {l_x} {Y_SIGN} {l_z} minecraft:bamboo_wall_hanging_sign[facing={sf1}]")
                        self.send_cmd(f"setblock {r_x} {Y_SIGN} {r_z} minecraft:bamboo_wall_hanging_sign[facing={sf2}]")
                    else:
                        # Wall + Lantern
                        self.send_cmd(f"setblock {l_x} {Y_LEDGE} {l_z} minecraft:{wall}")
                        self.send_cmd(f"setblock {r_x} {Y_LEDGE} {r_z} minecraft:{wall}")
                        self.send_cmd(f"setblock {l_x} {Y_SIGN} {l_z} minecraft:{wall}")
                        self.send_cmd(f"setblock {r_x} {Y_SIGN} {r_z} minecraft:{wall}")
                        self.send_cmd(f"setblock {l_x} {Y_LANTERN} {l_z} minecraft:lantern")
                        self.send_cmd(f"setblock {r_x} {Y_LANTERN} {r_z} minecraft:lantern")

            # Clean up dropped items in the DB area
            self.send_cmd(f"kill @e[type=item,x={CENTER_X-50},y=-64,z={CENTER_Z-50},dx=100,dy=100,dz=100]")

            print("[DB Ledger] World initialised successfully.")
            return True
        except Exception as e:
            print(f"[DB Error] init_world failed: {e}")
            return False

    def write_block(self, zone, record_id, record_dict):
        record_id = record_id.strip()
        seq = 0
        found = False
        while seq < 26: 
            x, y, z = self._get_coords(zone, seq)
            
            res = self.send_cmd(f"data get block {x} {y} {z} Book.tag.title")
            if "Found no elements" in res or "has no element" in res or "not a container" in res or "not a block entity" in res:
                break
            
            if record_id in res:
                found = True
                break
            seq += 1

        if seq >= 26:
            print(f"[DB Error] Zone {zone} is full!")
            return None

        x, y, z = self._get_coords(zone, seq)
        
        hashed_record = {}
        for k, v in record_dict.items():
            if k in ["id", "dt"]:
                hashed_record[k] = v
            else:
                hashed_record[k] = hashlib.sha256(str(v).encode('utf-8')).hexdigest()[:16]
        
        canonical = json.dumps(hashed_record)
        escaped = canonical.replace('"', '\\\\"')
        page_json = f'"{escaped}"'
        
        ax = "z" if zone in [0, 1] else "x"
        side = seq % 2
        fac = "east" if x == CENTER_X - 2 else "west"
        if zone in [2, 3]:
            fac = "south" if z == CENTER_Z - 2 else "north"

        book_nbt = f'{{Book:{{id:"minecraft:written_book",Count:1b,tag:{{title:"{record_id}",author:"DB_Sync",pages:[\'{page_json}\']}}}}}}'
        cmd = f"setblock {x} {y} {z} minecraft:lectern[has_book=true,facing={fac}]{book_nbt} replace"
        print("[DEBUG CMD]", cmd)
        
        self.send_cmd(f"setblock {x} {y} {z} minecraft:air replace")
        res_merge = self.send_cmd(cmd)

        if not found:
            # Update the Sign
            if zone in [0, 1]:
                sz = z
                sx = x
                sign_face = "west" if x == CENTER_X - 2 else "east"
            else:
                sx = x
                sz = z
                sign_face = "south" if z == CENTER_Z - 2 else "north"
                
            sign_y = Y_SIGN
            
            dt = format_date_ledger(record_dict.get('dt', 'N/A'), "dd-mm-yy")
            tc = "dark_red" if zone==2 else ("dark_blue" if zone==3 else ("gold" if zone==1 else "dark_green"))
            
            m1 = f'{{"text":"{record_id}","color":"{tc}","bold":true}}'
            m2 = f'{{"text":"Last Updated:","color":"black"}}'
            m3 = f'{{"text":"{dt}","color":"black"}}'
            m4 = f'{{"text":""}}'
            
            self.send_cmd(f"data merge block {sx} {sign_y} {sz} {{front_text:{{messages:['{m1}','{m2}','{m3}','{m4}']}}}}")

        # Clean up dropped items (e.g. replaced signs)
        self.send_cmd(f"kill @e[type=item,x={CENTER_X-50},y=-64,z={CENTER_Z-50},dx=100,dy=100,dz=100]")
        return {"status": "SUCCESS", "details": {"seq": seq, "updated": found, "x": x, "y": y, "z": z}}

    def read_block(self, zone: int, record_id: str) -> dict:
        record_id = record_id.strip()
        seq = 0
        while seq < 26:
            x, y, z = self._get_coords(zone, seq)
            res = self.send_cmd(f"data get block {x} {y} {z} Book.tag.title")
            if "Found no elements" in res or "has no element" in res or "not a container" in res or "not a block entity" in res:
                break
            if record_id in res:
                # Found the book! Read its pages.
                res_pages = self.send_cmd(f"data get block {x} {y} {z} Book.tag.pages[0]")
                # Parse the JSON string from the NBT output
                # Output looks like: ... has the following block data: '"{\\"id\\": \\"WRK-001\\"}"'
                try:
                    # Extract the string between the outermost single quotes
                    import re
                    match = re.search(r"data: '\"(.*?)\"'", res_pages)
                    if not match:
                        match = re.search(r'data: \'"(.*?)"\'', res_pages)
                    if match:
                        json_str = match.group(1).replace('\\\\"', '"').replace('\\"', '"')
                        return json.loads(json_str)
                    
                    # Alternative regex if formatting differs
                    match2 = re.search(r'data: "(.*?)"', res_pages)
                    if match2:
                        json_str = match2.group(1).replace('\\\\"', '"').replace('\\"', '"').strip('"')
                        return json.loads(json_str)
                except Exception as e:
                    print(f"Failed to parse read data: {e}")
                return None
            seq += 1
        return None

    def delete_block(self, zone: int, record_id: str) -> bool:
        record_id = record_id.strip()
        seq = 0
        while seq < 26:
            x, y, z = self._get_coords(zone, seq)
            res = self.send_cmd(f"data get block {x} {y} {z} Book.tag.title")
            if "Found no elements" in res or "has no element" in res or "not a container" in res or "not a block entity" in res:
                break
            if record_id in res:
                # Found the book! Clear it.
                fac = "east" if x == CENTER_X - 2 else "west"
                if zone in [2, 3]:
                    fac = "south" if z == CENTER_Z - 2 else "north"
                
                self.send_cmd(f"setblock {x} {y} {z} minecraft:air replace")
                self.send_cmd(f"setblock {x} {y} {z} minecraft:lectern[facing={fac}] replace")
                
                if zone in [0, 1]:
                    sx = x
                    sz = z
                else:
                    sx = x
                    sz = z
                self.send_cmd(f"data merge block {sx} {Y_SIGN} {sz} {{front_text:{{messages:['{{\"text\":\"\"}}','{{\"text\":\"\"}}','{{\"text\":\"\"}}','{{\"text\":\"\"}}']}}}}")
                self.send_cmd(f"kill @e[type=item,x={CENTER_X-50},y=-64,z={CENTER_Z-50},dx=100,dy=100,dz=100]")
                return True
            seq += 1
        return False

    def wipe_state(self):
        print("[DB Ledger] Wiping database state...")
        try:
            for zone in range(4):
                for seq in range(26):
                    x, y, z = self._get_coords(zone, seq)
                    fac = "east" if x == CENTER_X - 2 else "west"
                    if zone in [2, 3]:
                        fac = "south" if z == CENTER_Z - 2 else "north"
                        
                    self.send_cmd(f"setblock {x} {y} {z} minecraft:lectern[facing={fac}] replace")
                    
                    if zone in [0, 1]:
                        sx = x
                        sz = z
                    else:
                        sx = x
                        sz = z
                    self.send_cmd(f"setblock {sx} {Y_SIGN} {sz} minecraft:bamboo_wall_hanging_sign[facing={fac}] replace")
                    self.send_cmd(f"data merge block {sx} {Y_SIGN} {sz} {{front_text:{{messages:['{{\"text\":\"\"}}','{{\"text\":\"\"}}','{{\"text\":\"\"}}','{{\"text\":\"\"}}']}}}}")
            
            # Clean up dropped items
            self.send_cmd(f"kill @e[type=item,x={CENTER_X-50},y=-64,z={CENTER_Z-50},dx=100,dy=100,dz=100]")
            self.send_cmd("tp @a -50 -58 -50")
            return True
        except Exception as e:
            print(f"[DB Error] {e}")
            return False

if __name__ == "__main__":
    db = DatabaseLedger()
    if db.connect():
        db.init_world()
        db.disconnect()
