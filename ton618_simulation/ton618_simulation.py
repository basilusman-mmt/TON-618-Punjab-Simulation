import pygame
import math
import random
import sys

pygame.init()

W, H = 1280, 720
screen = pygame.display.set_mode((W, H), pygame.RESIZABLE)
pygame.display.set_caption("TON 618 | Punjab Simulation")
clock = pygame.time.Clock()

FONT = pygame.font.SysFont("arial", 20, bold=True)
SMALL = pygame.font.SysFont("arial", 14, bold=True)
BIG = pygame.font.SysFont("arial", 48, bold=True)

NEAR = .25
FOV = math.radians(80)
SENS = .002
GROUND = 1.7
GRAVITY = 22
JUMP = 8

player = pygame.Vector3(0, GROUND, -10)
yaw = 0
pitch = 0
vy = 0
grounded = True

elapsed = 0
running = True
locked = False
night = True
inside = False
house = None
dead = False
death_timer = 0
low_detail = False
third_person = False
camera_distance = 7.5
camera_height = 3.0
camera_smooth = player.copy()
camera_cached = player.copy()

caption = "A quiet evening in Punjab."
caption_timer = 8
mobile = False
touch_look = None
touch_move = None

BLACK_HOLE_START = 1800
BH_ACCEL = .00075

buildings = []
people = []
cars = []
birds = []
stars = []
trees = []
lamps = []
interior_people = []
render_queue = []

people_died = 0
collision_flash = 0

HOUSE_COLORS = [
    (170, 145, 115), (190, 165, 140),
    (140, 120, 100), (200, 175, 145),
    (155, 145, 130), (180, 155, 120),
    (130, 115, 105)
]

PERSON_COLORS = [
    (180, 65, 50), (50, 100, 160),
    (190, 175, 140), (65, 125, 75),
    (220, 205, 175), (100, 80, 140),
    (45, 45, 50), (190, 190, 180)
]

SKIN_COLORS = [
    (175, 125, 90), (195, 145, 105),
    (145, 95, 70), (210, 165, 125)
]

STAR_COLORS = [
    (255, 255, 255), (210, 225, 255),
    (255, 235, 210), (190, 210, 255),
    (255, 245, 230), (220, 220, 255)
]

for _ in range(100400):
    stars.append({
        "az": random.uniform(-math.pi, math.pi),
        "el": random.uniform(-1.5, 1.5),
        "size": random.choices([1, 2, 3], [85, 14, 1])[0],
        "brightness": random.randint(90, 255),
        "speed": random.uniform(.1, 2),
        "phase": random.uniform(0, math.tau),
        "color": random.choice(STAR_COLORS)
    })


def clamp(v, a, b):
    return max(a, min(v, b))


def shade(c, f):
    return tuple(clamp(int(x * f), 0, 255) for x in c)


def set_caption(text, duration=5):
    global caption, caption_timer
    caption = text
    caption_timer = duration


def distance(x1, z1, x2, z2):
    return math.hypot(x1 - x2, z1 - z2)


def black_hole_distance():
    return BLACK_HOLE_START * math.exp(-BH_ACCEL * elapsed * elapsed)


def black_hole_position():
    remaining = max(1, black_hole_distance())
    return pygame.Vector3(0, player.y + 250, player.z + remaining)


def threat_level():
    remaining = black_hole_distance()
    return clamp(1 - remaining / BLACK_HOLE_START, 0, 1)


def flee_direction(x, z):
    bh = black_hole_position()
    dx = x - bh.x
    dz = z - bh.z
    length = math.hypot(dx, dz)

    if length < .001:
        return pygame.Vector2(0, -1)

    return pygame.Vector2(dx / length, dz / length)


def update_camera(dt):
    global camera_cached

    if not third_person:
        camera_cached = player.copy()
        return

    forward = pygame.Vector3(math.sin(yaw), 0, math.cos(yaw))

    target = pygame.Vector3(
        player.x - forward.x * camera_distance,
        player.y + camera_height,
        player.z - forward.z * camera_distance
    )

    alpha = 1 - math.exp(-9 * dt)
    camera_cached.lerp(target, alpha)

    camera_cached.x = clamp(camera_cached.x, player.x - 30, player.x + 30)
    camera_cached.z = clamp(camera_cached.z, player.z - 30, player.z + 30)


def camera_position():
    return camera_cached.copy()


def camera_point(p):
    cam = camera_position()
    rel = pygame.Vector3(p) - cam

    cy, sy = math.cos(yaw), math.sin(yaw)
    x = rel.x * cy - rel.z * sy
    z = rel.x * sy + rel.z * cy

    cp, sp = math.cos(pitch), math.sin(pitch)
    y = rel.y * cp - z * sp
    depth = rel.y * sp + z * cp

    return x, y, depth


def current_fov():
    threat = threat_level()
    return FOV + math.radians(22) * threat ** 2


def project_camera(x, y, depth):
    w, h = screen.get_size()
    focal = w * .5 / math.tan(current_fov() * .5)

    return (
        w / 2 + x * focal / depth,
        h / 2 - y * focal / depth,
        depth
    )


def project(p):
    x, y, z = camera_point(p)

    if z <= NEAR:
        return None

    return project_camera(x, y, z)


def clip_polygon(vertices):
    out = []

    for i in range(len(vertices)):
        c = vertices[i]
        p = vertices[i - 1]

        cx, cy, cz = c
        px, py, pz = p

        ci = cz >= NEAR
        pi = pz >= NEAR

        if ci != pi:
            t = (NEAR - pz) / (cz - pz)
            out.append((
                px + (cx - px) * t,
                py + (cy - py) * t,
                NEAR
            ))

        if ci:
            out.append(c)

    return out


def poly3(points, color):
    cv = clip_polygon([camera_point(p) for p in points])

    if len(cv) < 3:
        return

    pp = [project_camera(*p) for p in cv]
    pts = [(int(p[0]), int(p[1])) for p in pp]
    avg = sum(p[2] for p in cv) / len(cv)

    render_queue.append((
        avg,
        lambda pts=pts, col=color: pygame.draw.polygon(screen, col, pts)
    ))


def line3(a, b, color, width=1):
    ca = camera_point(a)
    cb = camera_point(b)

    if ca[2] <= NEAR and cb[2] <= NEAR:
        return

    if ca[2] <= NEAR:
        t = (NEAR - ca[2]) / (cb[2] - ca[2])
        ca = tuple(ca[i] + (cb[i] - ca[i]) * t for i in range(3))

    if cb[2] <= NEAR:
        t = (NEAR - cb[2]) / (ca[2] - cb[2])
        cb = tuple(cb[i] + (ca[i] - cb[i]) * t for i in range(3))

    pa = project_camera(*ca)
    pb = project_camera(*cb)

    pts = (
        (int(pa[0]), int(pa[1])),
        (int(pb[0]), int(pb[1]))
    )

    render_queue.append((
        (ca[2] + cb[2]) / 2,
        lambda pts=pts, col=color, wid=width:
        pygame.draw.line(screen, col, pts[0], pts[1], max(1, wid))
    ))


def flush():
    render_queue.sort(key=lambda item: item[0], reverse=True)

    for _, fn in render_queue:
        fn()

    render_queue.clear()


def generate_buildings():
    buildings.clear()

    for row in range(120):
        z = row * 18 - 120

        for side in (-1, 1):
            buildings.append({
                "x": side * random.uniform(12, 19),
                "z": z + random.uniform(-3, 3),
                "w": random.uniform(5, 9),
                "d": random.uniform(7, 12),
                "h": random.uniform(6, 18),
                "color": random.choice(HOUSE_COLORS),
                "occupied": random.random() < .95
            })


def recycle_buildings():
    for b in buildings:
        if b["z"] < player.z - 120:
            b["z"] += 2160
            b["x"] = random.choice([-1, 1]) * random.uniform(12, 19)
            b["h"] = random.uniform(6, 18)
            b["w"] = random.uniform(5, 9)
            b["d"] = random.uniform(7, 12)
            b["color"] = random.choice(HOUSE_COLORS)
            b["occupied"] = random.random() < .95


def generate_people():
    people.clear()

    for _ in range(500):
        people.append({
            "x": random.choice([-1, 1]) * random.uniform(5.5, 9),
            "z": random.uniform(-100, 1800),
            "speed": random.uniform(2, 4),
            "direction": random.choice([-1, 1]),
            "color": random.choice(PERSON_COLORS),
            "skin": random.choice(SKIN_COLORS),
            "state": "normal",
            "phase": random.random() * math.tau,
            "turn": random.uniform(-1, 1),
            "dead_timer": 0,
            "hit_by": None
        })


def generate_cars():
    cars.clear()

    for _ in range(28):
        cars.append({
            "x": random.choice([-5.3, 5.3]),
            "z": random.uniform(-100, 1400),
            "speed": random.uniform(5, 18),
            "base_speed": random.uniform(5, 18),
            "direction": random.choice([-1, 1]),
            "color": random.choice([
                (160, 30, 35), (45, 45, 55),
                (210, 210, 210), (30, 90, 140),
                (190, 150, 50), (90, 90, 90),
                (40, 115, 75), (170, 170, 180)
            ]),
            "width": random.uniform(1.7, 2.2),
            "length": random.uniform(3.8, 5.4),
            "fleeing": False,
            "hit_cooldown": 0,
            "brake_lights": False
        })


def generate_birds():
    birds.clear()

    for _ in range(60):
        birds.append({
            "x": random.uniform(-150, 150),
            "y": random.uniform(12, 100),
            "z": random.uniform(-800, 1500),
            "speed": random.uniform(3, 18),
            "phase": random.random() * math.tau,
            "fleeing": False
        })


def generate_trees():
    trees.clear()

    for z in range(-100, 1800, 20):
        for side in (-1, 1):
            trees.append((side * random.uniform(10, 13), z))


def generate_lamps():
    lamps.clear()

    for z in range(-100, 1800, 30):
        lamps.extend([(-9.5, z), (9.5, z)])


def collision(x, z):
    for b in buildings:
        x0 = b["x"] - b["w"] / 2
        x1 = b["x"] + b["w"] / 2
        z0 = b["z"] - b["d"] / 2
        z1 = b["z"] + b["d"] / 2

        if x0 < x < x1 and z0 < z < z1:
            road_side = -1 if b["x"] > 0 else 1
            door_x = x0 if road_side == -1 else x1

            if abs(x - door_x) < 1.3 and abs(z - b["z"]) < 1.3:
                continue

            return True

    return False


def move_player(dx, dz):
    nx = player.x + dx

    if not collision(nx, player.z):
        player.x = nx

    nz = player.z + dz

    if not collision(player.x, nz):
        player.z = nz


def draw_building(b):
    x, z, w, d, h, c = (
        b["x"], b["z"], b["w"],
        b["d"], b["h"], b["color"]
    )

    if abs(z - player.z) > 300:
        return

    x0, x1 = x - w / 2, x + w / 2
    z0, z1 = z - d / 2, z + d / 2

    road_side = -1 if x > 0 else 1
    front_x = x0 if road_side == -1 else x1
    facade = front_x + road_side * .055

    poly3([
        (x0, 0, z0), (x1, 0, z0),
        (x1, h, z0), (x0, h, z0)
    ], shade(c, .55))

    poly3([
        (x0, 0, z1), (x1, 0, z1),
        (x1, h, z1), (x0, h, z1)
    ], shade(c, .35))

    poly3([
        (x0, 0, z0), (x0, 0, z1),
        (x0, h, z1), (x0, h, z0)
    ], shade(c, .43))

    poly3([
        (x1, 0, z0), (x1, 0, z1),
        (x1, h, z1), (x1, h, z0)
    ], shade(c, .35))

    poly3([
        (x0, h, z0), (x1, h, z0),
        (x1, h, z1), (x0, h, z1)
    ], shade(c, .7))

    poly3([
        (x0 - .3, h, z0 - .3),
        (x1 + .3, h, z0 - .3),
        (x1 + .3, h, z1 + .3),
        (x0 - .3, h, z1 + .3)
    ], (75, 45, 35))

    door_w = min(1.3, d * .22)
    door_h = min(2.8, h * .6)
    door_z = z

    poly3([
        (facade, 0, door_z - door_w / 2),
        (facade, 0, door_z + door_w / 2),
        (facade, door_h, door_z + door_w / 2),
        (facade, door_h, door_z - door_w / 2)
    ], (45, 25, 20))

    line3(
        (facade + road_side * .025, door_h * .48, door_z + door_w * .3),
        (facade + road_side * .035, door_h * .48, door_z + door_w * .3),
        (210, 175, 95), 3
    )

    if abs(z - player.z) < 120 and not low_detail:
        floors = max(1, min(4, int(h / 3.2)))
        columns = max(2, min(5, int(d / 2.1)))

        usable_height = h - 2.0
        floor_spacing = usable_height / floors
        usable_width = d - 1.8
        window_spacing = usable_width / columns
        window_w = min(1.15, window_spacing * .58)
        window_h = min(1.35, floor_spacing * .48)

        for floor in range(floors):
            wy = 1.0 + floor_spacing * (floor + .5)

            for col in range(columns):
                wz = z - usable_width / 2 + window_spacing * (col + .5)

                if abs(wz - door_z) < door_w * .85 and wy < door_h + .5:
                    continue

                left = wz - window_w / 2
                right = wz + window_w / 2
                bottom = wy - window_h / 2
                top = wy + window_h / 2

                frame = (55, 40, 32)
                lit = night and ((floor + col + int(b["z"] * 2)) % 4 != 0)
                glass = (255, 190, 105) if lit else (35, 55, 75)

                poly3([
                    (facade + road_side * .025, bottom - .09, left - .09),
                    (facade + road_side * .025, bottom - .09, right + .09),
                    (facade + road_side * .025, top + .09, right + .09),
                    (facade + road_side * .025, top + .09, left - .09)
                ], frame)

                poly3([
                    (facade + road_side * .045, bottom, left),
                    (facade + road_side * .045, bottom, right),
                    (facade + road_side * .045, top, right),
                    (facade + road_side * .045, top, left)
                ], glass)

                line3(
                    (facade + road_side * .06, bottom, wz),
                    (facade + road_side * .06, top, wz),
                    frame, 2
                )

                line3(
                    (facade + road_side * .06, wy, left),
                    (facade + road_side * .06, wy, right),
                    frame, 2
                )


def draw_road():
    z = player.z

    poly3([
        (-200, -.1, z - 150), (200, -.1, z - 150),
        (200, -.1, z + 1200), (-200, -.1, z + 1200)
    ], (30, 30, 33) if night else (85, 85, 80))

    poly3([
        (-9, 0, z - 150), (9, 0, z - 150),
        (9, 0, z + 1200), (-9, 0, z + 1200)
    ], (42, 42, 43) if night else (100, 100, 95))

    for side in (-1, 1):
        poly3([
            (side * 9, .02, z - 150),
            (side * 11, .02, z - 150),
            (side * 11, .02, z + 1200),
            (side * 9, .02, z + 1200)
        ], (70, 55, 40) if night else (130, 115, 100))

    for zz in range(int(z - 150), int(z + 1200), 14):
        poly3([
            (-.12, .035, zz), (.12, .035, zz),
            (.12, .035, zz + 6), (-.12, .035, zz + 6)
        ], (120, 110, 80))


def draw_trees():
    for x, z in trees:
        if abs(z - player.z) > 200:
            continue

        line3((x, 0, z), (x, 7, z), (60, 40, 25), 4)

        if not low_detail:
            for i in range(6):
                a = i * math.tau / 6
                line3(
                    (x, 6, z),
                    (x + math.cos(a) * 3, 7, z + math.sin(a) * 3),
                    (35, 75, 35), 3
                )


def draw_lamps():
    for x, z in lamps:
        if abs(z - player.z) > 150:
            continue

        line3((x, 0, z), (x, 8, z), (55, 55, 60), 3)
        line3((x, 8, z), (x + .8, 8, z), (55, 55, 60), 2)

        if night and abs(z - player.z) < 70:
            p = project((x + .8, 7.8, z))

            if p:
                sx, sy, d = p
                r = int(clamp(100 / d, 2, 25))
                pygame.draw.circle(screen, (255, 210, 130), (int(sx), int(sy)), r)


def draw_car(car):
    x, z = car["x"], car["z"]
    w, length = car["width"], car["length"]
    c = car["color"]

    if abs(z - player.z) > 180:
        return

    x0, x1 = x - w / 2, x + w / 2
    z0, z1 = z - length / 2, z + length / 2

    front_z = z0 if car["direction"] > 0 else z1
    rear_z = z1 if car["direction"] > 0 else z0

    body_bottom = .18
    body_top = .95
    roof_top = 1.65

    poly3([
        (x0, body_bottom, z0), (x1, body_bottom, z0),
        (x1, body_bottom, z1), (x0, body_bottom, z1)
    ], shade(c, .45))

    poly3([
        (x0, body_bottom, z0), (x0, body_bottom, z1),
        (x0, body_top, z1), (x0, body_top, z0)
    ], shade(c, .65))

    poly3([
        (x1, body_bottom, z0), (x1, body_bottom, z1),
        (x1, body_top, z1), (x1, body_top, z0)
    ], shade(c, .78))

    poly3([
        (x0, body_top, z0), (x1, body_top, z0),
        (x1, body_top, z1), (x0, body_top, z1)
    ], shade(c, 1.12))

    cabin_front = z - length * .25
    cabin_back = z + length * .25

    poly3([
        (x - w * .39, body_top, cabin_front),
        (x + w * .39, body_top, cabin_front),
        (x + w * .31, roof_top, cabin_front + .35),
        (x - w * .31, roof_top, cabin_front + .35)
    ], shade(c, .9))

    poly3([
        (x - w * .31, roof_top, cabin_front + .35),
        (x + w * .31, roof_top, cabin_front + .35),
        (x + w * .31, roof_top, cabin_back - .3),
        (x - w * .31, roof_top, cabin_back - .3)
    ], shade(c, 1.15))

    poly3([
        (x - w * .31, roof_top, cabin_back - .3),
        (x + w * .31, roof_top, cabin_back - .3),
        (x + w * .4, body_top, cabin_back),
        (x - w * .4, body_top, cabin_back)
    ], shade(c, .7))

    poly3([
        (x - w * .35, body_top + .03, cabin_front + .12),
        (x + w * .35, body_top + .03, cabin_front + .12),
        (x + w * .28, roof_top - .08, cabin_front + .42),
        (x - w * .28, roof_top - .08, cabin_front + .42)
    ], (35, 55, 70))

    poly3([
        (x - w * .28, roof_top - .08, cabin_back - .38),
        (x + w * .28, roof_top - .08, cabin_back - .38),
        (x + w * .36, body_top + .03, cabin_back - .05),
        (x - w * .36, body_top + .03, cabin_back - .05)
    ], (30, 45, 60))

    for side in (-1, 1):
        sx = x + side * w * .405

        poly3([
            (sx, body_top + .08, cabin_front + .45),
            (sx, body_top + .08, cabin_back - .42),
            (sx, roof_top - .05, cabin_back - .4),
            (sx, roof_top - .05, cabin_front + .45)
        ], (45, 70, 85))

        line3(
            (sx, body_top + .04, cabin_front + .48),
            (sx, body_top + .04, cabin_back - .45),
            shade(c, .5), 2
        )

        line3(
            (sx, body_top + .03, z),
            (sx, roof_top - .05, z),
            shade(c, .5), 2
        )

        mirror_x = x + side * w * .57
        line3(
            (sx, 1.05, cabin_front + .3),
            (mirror_x, 1.1, cabin_front + .3),
            shade(c, .5), 2
        )

        poly3([
            (mirror_x - .08, 1.02, cabin_front + .2),
            (mirror_x + .08, 1.02, cabin_front + .2),
            (mirror_x + .08, 1.2, cabin_front + .2),
            (mirror_x - .08, 1.2, cabin_front + .2)
        ], shade(c, .7))

    for wheel_z in (z0 + .8, z1 - .8):
        for side in (-1, 1):
            wx = x + side * w * .47

            wheel = [
                (wx - .13, .12, wheel_z - .3),
                (wx + .13, .12, wheel_z - .3),
                (wx + .13, .78, wheel_z - .3),
                (wx - .13, .78, wheel_z - .3)
            ]

            poly3(wheel, (12, 12, 14))

            p = project((wx, .45, wheel_z - .31))

            if p:
                sx, sy, depth = p
                r = max(2, int(8 / max(depth / 12, .3)))
                pygame.draw.circle(screen, (115, 115, 120), (int(sx), int(sy)), r)
                pygame.draw.circle(screen, (35, 35, 38), (int(sx), int(sy)), max(1, r // 2))

    for side in (-1, 1):
        lx = x + side * w * .31

        if car["direction"] > 0:
            light_z = front_z
            light_color = (255, 240, 190) if night else (220, 220, 200)
        else:
            light_z = rear_z
            light_color = (255, 35, 25) if car["brake_lights"] else (180, 30, 25)

        poly3([
            (lx - .13, .55, light_z),
            (lx + .13, .55, light_z),
            (lx + .13, .85, light_z),
            (lx - .13, .85, light_z)
        ], light_color)

        if night and car["direction"] > 0:
            p = project((lx, .7, light_z))

            if p:
                sx, sy, depth = p
                r = int(clamp(120 / depth, 2, 15))
                pygame.draw.circle(screen, (255, 235, 170), (int(sx), int(sy)), r)

    bumper_color = (55, 55, 58)

    poly3([
        (x - w * .42, .2, front_z),
        (x + w * .42, .2, front_z),
        (x + w * .42, .42, front_z),
        (x - w * .42, .42, front_z)
    ], bumper_color)

    poly3([
        (x - w * .42, .2, rear_z),
        (x + w * .42, .2, rear_z),
        (x + w * .42, .42, rear_z),
        (x - w * .42, .42, rear_z)
    ], bumper_color)

    line3(
        (x - w * .25, body_top + .02, z - length * .1),
        (x + w * .25, body_top + .02, z - length * .1),
        shade(c, .55), 2
    )

    line3(
        (x - w * .25, body_top + .02, z + length * .1),
        (x + w * .25, body_top + .02, z + length * .1),
        shade(c, .55), 2
    )


def draw_birds():
    for bird in birds:
        if abs(bird["z"] - player.z) > 1000:
            continue

        p = project((bird["x"], bird["y"], bird["z"]))

        if not p:
            continue

        sx, sy, d = p
        scale = clamp(60 / d, .2, 5)
        wing = math.sin(elapsed * 8 + bird["phase"]) * 5 * scale

        pygame.draw.line(
            screen, (35, 35, 35),
            (int(sx - 8 * scale), int(sy + wing)),
            (int(sx), int(sy)), max(1, int(scale))
        )

        pygame.draw.line(
            screen, (35, 35, 35),
            (int(sx), int(sy)),
            (int(sx + 8 * scale), int(sy + wing)),
            max(1, int(scale))
        )


def draw_person(p):
    x, z = p["x"], p["z"]
    phase = p["phase"]
    running_person = p["state"] == "panic"

    if p["state"] == "dead":
        body_color = shade(p["color"], .65)

        poly3([
            (x - .28, .08, z - .55),
            (x + .28, .08, z - .55),
            (x + .28, .08, z + .55),
            (x - .28, .08, z + .55)
        ], body_color)

        poly3([
            (x - .32, .1, z + .45),
            (x + .32, .1, z + .45),
            (x + .2, .1, z + .85),
            (x - .2, .1, z + .85)
        ], p["skin"])

        return

    stride = math.sin(phase) * (.5 if running_person else .23)
    arm_swing = math.sin(phase + 1.5) * (.55 if running_person else .25)

    hip_y = .85
    shoulder_y = 1.25
    head_y = 1.55

    torso_w = .22

    poly3([
        (x - torso_w, hip_y, z),
        (x + torso_w, hip_y, z),
        (x + torso_w * .72, shoulder_y, z),
        (x - torso_w * .72, shoulder_y, z)
    ], p["color"])

    line3(
        (x - .12, hip_y, z),
        (x - .17 + stride, .12, z),
        (25, 25, 28), 5
    )

    line3(
        (x + .12, hip_y, z),
        (x + .17 - stride, .12, z),
        (25, 25, 28), 5
    )

    line3(
        (x - .15, shoulder_y, z),
        (x - .35 - arm_swing, .72, z),
        p["skin"], 4
    )

    line3(
        (x + .15, shoulder_y, z),
        (x + .35 + arm_swing, .72, z),
        p["skin"], 4
    )

    poly3([
        (x - .15, 1.2, z),
        (x + .15, 1.2, z),
        (x + .13, 1.32, z),
        (x - .13, 1.32, z)
    ], p["skin"])

    head_radius = .13

    head = project((x, head_y, z))

    if head:
        sx, sy, depth = head
        radius = max(2, int(90 / depth * head_radius * 2.5))
        pygame.draw.circle(screen, p["skin"], (int(sx), int(sy)), radius)

        if depth < 65 and radius >= 4:
            eye_y = int(sy - radius * .05)
            eye_offset = max(1, radius // 3)

            pygame.draw.circle(screen, (25, 20, 18), (int(sx - eye_offset), eye_y), max(1, radius // 9))
            pygame.draw.circle(screen, (25, 20, 18), (int(sx + eye_offset), eye_y), max(1, radius // 9))

            if running_person:
                pygame.draw.ellipse(
                    screen, (55, 10, 10),
                    (int(sx - radius * .2), int(sy + radius * .2),
                     max(2, int(radius * .4)), max(2, int(radius * .5)))
                )


def draw_people():
    if third_person:
        draw_player_model()

    for p in people:
        if abs(p["z"] - player.z) > 140:
            continue

        cp = camera_point((p["x"], 1, p["z"]))

        if cp[2] <= NEAR:
            continue

        render_queue.append((cp[2], lambda item=p: draw_person(item)))


def draw_player_model():
    if not third_person:
        return

    player_character = {
        "x": player.x,
        "z": player.z,
        "color": (45, 100, 190),
        "skin": (190, 145, 110),
        "state": "normal",
        "phase": elapsed * 8
    }

    cp = camera_point((player.x, 1, player.z))

    if cp[2] <= NEAR:
        return

    render_queue.append((
        cp[2],
        lambda item=player_character: draw_person(item)
    ))


def panic_person(p):
    if p["state"] in ("panic", "dead"):
        return

    p["state"] = "panic"
    p["speed"] = random.uniform(5, 8)


def update_people(dt):
    threat = threat_level()

    for p in people:
        if p["state"] == "dead":
            p["dead_timer"] += dt
            continue

        if threat > .12 and random.random() < dt * threat * .8:
            panic_person(p)

        if p["state"] == "panic":
            direction = flee_direction(p["x"], p["z"])
            speed = p["speed"] * (1 + threat * 1.5)

            p["x"] += direction.x * speed * dt
            p["z"] += direction.y * speed * dt
            p["x"] += p["turn"] * dt * 1.5
            p["x"] = clamp(p["x"], -35, 35)

            if p["z"] < player.z - 100:
                p["z"] = player.z + random.uniform(400, 1500)
                p["x"] = random.choice([-1, 1]) * random.uniform(5, 9)
                p["state"] = "normal"

        else:
            p["z"] += p["direction"] * p["speed"] * .25 * dt

    for p in people:
        if p["state"] != "normal":
            continue

        for other in people:
            if other["state"] == "panic":
                if distance(p["x"], p["z"], other["x"], other["z"]) < 15:
                    if random.random() < dt * 2.5:
                        panic_person(p)
                        break


def check_car_collisions():
    global people_died, collision_flash

    for car in cars:
        if abs(car["z"] - player.z) > 160:
            continue

        half_length = car["length"] * .5
        half_width = car["width"] * .5

        for p in people:
            if p["state"] == "dead":
                continue

            dx = abs(p["x"] - car["x"])
            dz = abs(p["z"] - car["z"])

            if dx < half_width + .35 and dz < half_length + .35:
                p["state"] = "dead"
                p["dead_timer"] = 0
                p["hit_by"] = car
                people_died += 1
                collision_flash = .3

                p["x"] += random.uniform(-.3, .3)
                p["z"] += random.uniform(-.5, .5)


def update_cars(dt, threat):
    for car in cars:
        car["hit_cooldown"] = max(0, car["hit_cooldown"] - dt)
        car["brake_lights"] = False

        if threat > .15:
            car["speed"] = max(0, car["speed"] - (5 + threat * 30) * dt)
            car["brake_lights"] = True

        if threat > .4:
            car["fleeing"] = True
            car["direction"] = -1

        if car["fleeing"]:
            car["speed"] = min(30, car["speed"] + 12 * dt)
        elif threat < .1:
            car["speed"] += (car["base_speed"] - car["speed"]) * dt

        car["z"] += car["direction"] * car["speed"] * dt

        if car["z"] < player.z - 100:
            car["z"] = player.z + random.uniform(300, 1200)
            car["speed"] = random.uniform(5, 18)
            car["base_speed"] = car["speed"]
            car["direction"] = random.choice([-1, 1])
            car["fleeing"] = False

        if car["z"] > player.z + 1600:
            car["z"] = player.z - 80
            car["direction"] = 1
            car["fleeing"] = False


def update_birds(dt, threat):
    for bird in birds:
        if threat > .2:
            bird["fleeing"] = True

        if bird["fleeing"]:
            bird["y"] += dt * 8
            bird["x"] += bird["speed"] * dt * 2
            bird["z"] -= bird["speed"] * dt * 2
        else:
            bird["x"] += bird["speed"] * dt
            bird["z"] += bird["speed"] * dt * .6

        if bird["x"] > 180 or bird["y"] > 180:
            bird["x"] = -180
            bird["z"] = player.z + random.uniform(-800, 1500)
            bird["y"] = random.uniform(12, 100)
            bird["fleeing"] = False


def alert_crowd():
    set_caption("HEY! LOOK AT THE SKY!", 5)

    for p in people:
        if p["state"] != "dead" and distance(p["x"], p["z"], player.x, player.z) < 65:
            panic_person(p)

    if inside:
        alert_interior()


def draw_sky():
    w, h = screen.get_size()

    if night:
        screen.fill((3, 5, 16))
    else:
        for i in range(12):
            col = (100 + i * 5, 155 + i * 3, 210 + i * 2)
            pygame.draw.rect(screen, col, (0, i * h // 12, w, h // 12 + 1))

    if not night:
        return

    focal = w * .65
    threat = threat_level()
    bh = black_hole_position()
    bh_cam = camera_point(bh)

    if bh_cam[2] > NEAR:
        bh_x = w / 2 + bh_cam[0] * focal / bh_cam[2]
        bh_y = h / 2 - bh_cam[1] * focal / bh_cam[2]
    else:
        bh_x, bh_y = w / 2, h / 2

    lens_strength = clamp(threat ** 2 * 2.2, 0, 1.5)
    lens_radius = clamp(120 + threat * 550, 120, 650)

    star_step = 1 if not low_detail else 4

    for index in range(0, len(stars), star_step):
        star = stars[index]
        dx = (star["az"] - yaw + math.pi) % math.tau - math.pi
        dy = star["el"] - pitch

        if abs(dx) > 1.55 or abs(dy) > 1.55:
            continue

        sx = w / 2 + math.tan(dx) * focal
        sy = h / 2 - math.tan(dy) * focal

        if lens_strength > .01:
            ox = sx - bh_x
            oy = sy - bh_y
            r2 = ox * ox + oy * oy

            if r2 > 1:
                radius = math.sqrt(r2)
                deflection = lens_strength * lens_radius * lens_radius / (radius * radius + lens_radius * 3)
                deflection = min(deflection, lens_radius * .45)
                sx += ox / radius * deflection
                sy += oy / radius * deflection

        if sx < -30 or sx > w + 30 or sy < -30 or sy > h + 30:
            continue

        twinkle = math.sin(elapsed * star["speed"] + star["phase"])
        brightness = int(clamp(star["brightness"] + twinkle * 25, 30, 255))
        color = tuple(c * brightness // 255 for c in star["color"])

        pygame.draw.circle(screen, color, (int(sx), int(sy)), star["size"])


def draw_black_hole(threat):
    bh = black_hole_position()
    p = project(bh)

    if not p:
        return

    sx, sy, depth = p
    remaining = black_hole_distance()
    approach = 1 - remaining / BLACK_HOLE_START

    radius = int(clamp(800 / max(depth, 1) * (1 + approach * 5), 5, 350))

    if radius <= 0:
        return

    glow_radius = int(clamp(radius * 9, 80, 1200))

    if not low_detail:
        glow = pygame.Surface((glow_radius * 2, glow_radius * 2), pygame.SRCALPHA)
        cx = cy = glow_radius

        for i in range(12, 0, -1):
            r = int(radius * (1.2 + i * .7))
            pygame.draw.circle(
                glow,
                (255, 90, 15, 7 + i * 2),
                (cx, cy), max(1, r)
            )

        disk_w = max(10, radius * 10)
        disk_h = max(8, radius * 3)
        disk = pygame.Surface((disk_w, disk_h), pygame.SRCALPHA)

        pygame.draw.ellipse(disk, (255, 80, 10, 180), (0, 0, disk_w, disk_h))
        pygame.draw.ellipse(
            disk, (255, 180, 65, 235),
            (disk_w * .08, disk_h * .23, disk_w * .84, disk_h * .54)
        )
        pygame.draw.ellipse(
            disk, (255, 245, 210, 245),
            (disk_w * .25, disk_h * .38, disk_w * .5, disk_h * .24)
        )

        glow.blit(disk, disk.get_rect(center=(cx, cy)))

        jet_length = int(clamp(2500 / depth * (1 + threat * 10), 30, 1600))

        for side in (-1, 1):
            pygame.draw.line(
                glow, (140, 180, 255, 100),
                (cx, cy), (cx, cy + side * jet_length),
                max(1, radius // 5)
            )

        screen.blit(glow, (int(sx - cx), int(sy - cy)))

    pygame.draw.ellipse(
        screen, (255, 105, 20),
        (int(sx - radius * 2.7), int(sy - radius * .65),
         int(radius * 5.4), int(radius * 1.3))
    )

    pygame.draw.ellipse(
        screen, (255, 210, 120),
        (int(sx - radius * 2.2), int(sy - radius * .35),
         int(radius * 4.4), int(radius * .7))
    )

    pygame.draw.ellipse(
        screen, (255, 250, 225),
        (int(sx - radius * 1.5), int(sy - radius * .16),
         int(radius * 3), int(radius * .32))
    )

    pygame.draw.circle(screen, (0, 0, 0), (int(sx), int(sy)), radius)

    pygame.draw.circle(
        screen, (255, 220, 160),
        (int(sx), int(sy)), max(1, int(radius * .95)), max(1, radius // 18)
    )

    if threat > .5 and not low_detail:
        for i in range(6):
            a = elapsed * .35 + i * math.tau / 6
            orbit = radius * (2.5 + math.sin(elapsed + i) * .15)

            px = sx + math.cos(a) * orbit
            py = sy + math.sin(a) * orbit * .35

            pygame.draw.circle(
                screen, (255, 160, 80),
                (int(px), int(py)), max(1, radius // 20)
            )


def draw_lens_distortion(threat):
    if threat < .08:
        return

    w, h = screen.get_size()
    strength = threat ** 2
    overlay = pygame.Surface((w, h), pygame.SRCALPHA)

    if strength > .15:
        count = int(10 + strength * 45)

        for i in range(count):
            y = random.randint(0, h)
            x = random.randint(0, w)
            length = random.randint(10, int(30 + strength * 180))
            alpha = random.randint(8, int(20 + strength * 65))

            pygame.draw.line(
                overlay,
                (220, 225, 255, alpha),
                (x, y),
                (x + length, y + random.randint(-3, 3)),
                random.choice([1, 1, 2])
            )

    if strength > .35:
        edge = int(20 + strength * 120)
        pygame.draw.rect(
            overlay, (0, 0, 0, min(150, edge)),
            (0, 0, w, h), edge
        )

    if strength > .6:
        flash = int(clamp((strength - .6) * 100, 0, 65))
        overlay.fill((255, 245, 225, flash))

    screen.blit(overlay, (0, 0))


def find_house():
    for b in buildings:
        road_side = -1 if b["x"] > 0 else 1
        door_x = b["x"] + road_side * b["w"] / 2
        approach_x = door_x + road_side * 2.0

        if (
            abs(player.x - approach_x) < 3.5
            and abs(player.z - b["z"]) < max(2.8, b["d"] * .2)
        ):
            return b

    return None


def create_interior(b):
    global interior_people
    interior_people = []

    if not b["occupied"]:
        return

    for _ in range(random.randint(2, 7)):
        interior_people.append({
            "x": random.uniform(100, 650),
            "y": random.uniform(100, 450),
            "state": "normal",
            "panic": 0,
            "speed": random.uniform(80, 160),
            "color": random.choice(PERSON_COLORS),
            "skin": random.choice(SKIN_COLORS)
        })


def enter_house():
    global inside, house

    b = find_house()

    if b is None:
        set_caption("Move closer to a front door.", 3)
        return

    house = b
    inside = True
    create_interior(b)
    set_caption("You enter a house.", 5)
    pygame.mouse.set_visible(True)
    pygame.event.set_grab(False)


def leave_house():
    global inside, house

    if not inside or house is None:
        return

    b = house
    road_side = -1 if b["x"] > 0 else 1
    door_x = b["x"] + road_side * b["w"] / 2

    player.x = door_x + road_side * 2.5
    player.z = b["z"]
    player.y = GROUND

    inside = False
    house = None

    set_caption("You leave the house.", 5)
    pygame.mouse.set_visible(not locked)
    pygame.event.set_grab(locked)


def alert_interior():
    for p in interior_people:
        if p["state"] == "normal":
            p["state"] = "alert"
            p["panic"] = random.uniform(.5, 2)


def update_interior(dt, threat):
    for p in interior_people:
        if p["state"] == "escaped":
            continue

        if threat > .2 and p["state"] == "normal":
            p["state"] = "alert"
            p["panic"] = random.uniform(.5, 2)

        if p["state"] == "alert":
            p["panic"] -= dt

            if p["panic"] <= 0:
                p["state"] = "panic"

        elif p["state"] == "panic":
            p["x"] += (350 - p["x"]) * dt * .8
            p["y"] += (480 - p["y"]) * dt * .8

            if p["x"] > 310 and p["y"] > 420:
                p["state"] = "escaped"


def draw_interior():
    w, h = screen.get_size()
    screen.fill((30, 25, 20))

    floor = pygame.Rect(int(w * .08), int(h * .1), int(w * .84), int(h * .75))
    pygame.draw.rect(screen, (130, 105, 80), floor)

    pygame.draw.rect(
        screen, (160, 130, 100),
        (int(w * .1), int(h * .12), int(w * .8), int(h * .7))
    )

    wall = (95, 70, 55)

    pygame.draw.rect(screen, wall, (int(w * .1), int(h * .12), int(w * .8), 8))
    pygame.draw.rect(screen, wall, (int(w * .1), int(h * .12), 8, int(h * .7)))
    pygame.draw.rect(screen, wall, (int(w * .9) - 8, int(h * .12), 8, int(h * .7)))

    room_boxes = [
        (int(w * .12), int(h * .15), int(w * .36), int(h * .28)),
        (int(w * .5), int(h * .15), int(w * .36), int(h * .28)),
        (int(w * .12), int(h * .48), int(w * .36), int(h * .3)),
        (int(w * .5), int(h * .48), int(w * .36), int(h * .3))
    ]

    names = ["LIVING ROOM", "BEDROOM", "KITCHEN", "BEDROOM"]

    for i, rect in enumerate(room_boxes):
        pygame.draw.rect(screen, (115, 85, 65), rect)
        pygame.draw.rect(screen, (60, 45, 35), rect, 4)
        screen.blit(SMALL.render(names[i], True, (255, 235, 210)), (rect[0] + 8, rect[1] + 8))

    lx, ly, lw, lh = room_boxes[0]
    pygame.draw.rect(screen, (65, 80, 75), (lx + 40, ly + 55, lw - 80, 65))
    pygame.draw.rect(screen, (45, 45, 50), (lx + 40, ly + 130, 90, 40))

    kx, ky, kw, kh = room_boxes[2]
    pygame.draw.rect(screen, (80, 80, 80), (kx + 20, ky + 30, kw - 40, 40))
    pygame.draw.rect(screen, (80, 80, 80), (kx + 20, ky + 90, 80, 80))

    for i in range(2):
        bx, by, bw, bh = room_boxes[1 + i]
        pygame.draw.rect(screen, (90, 65, 50), (bx + 30, by + 60, bw - 60, 80))
        pygame.draw.rect(screen, (180, 160, 140), (bx + 30, by + 60, bw - 60, 25))

    pygame.draw.rect(screen, (55, 35, 25), (int(w * .43), int(h * .75), int(w * .14), int(h * .1)))

    for p in interior_people:
        if p["state"] == "escaped":
            continue

        x, y = int(p["x"]), int(p["y"])
        pygame.draw.circle(screen, p["skin"], (x, y), 12)
        pygame.draw.rect(screen, p["color"], (x - 10, y + 10, 20, 35))

        if p["state"] in ("panic", "alert"):
            pygame.draw.circle(screen, (40, 10, 10), (x - 3, y - 2), 3)
            pygame.draw.circle(screen, (40, 10, 10), (x + 3, y - 2), 3)

    title = BIG.render("HOUSE INTERIOR", True, (255, 240, 220))
    screen.blit(title, (w // 2 - title.get_width() // 2, 25))

    screen.blit(SMALL.render("E: EXIT | F: ALERT PEOPLE", True, (255, 230, 200)), (20, h - 45))


def draw_caption():
    w, h = screen.get_size()

    if caption_timer <= 0:
        return

    box = pygame.Surface((w, 90), pygame.SRCALPHA)
    box.fill((0, 0, 0, 170))
    screen.blit(box, (0, h - 100))

    image = FONT.render(caption, True, (255, 235, 210))
    screen.blit(image, (w // 2 - image.get_width() // 2, h - 65))


def draw_hud(threat):
    w, h = screen.get_size()

    if inside or dead:
        return

    info = SMALL.render(
        f"TON 618 | THREAT: {threat * 100:.1f}% | "
        f"{'NIGHT' if night else 'DAY'} | "
        f"{'THIRD PERSON' if third_person else 'FIRST PERSON'}",
        True, (220, 220, 230)
    )

    screen.blit(info, (15, 15))

    remaining = black_hole_distance()

    distance_text = SMALL.render(
        f"SIMULATED DISTANCE: {remaining:,.2f} AU",
        True, (255, 190, 130)
    )

    screen.blit(distance_text, (15, 38))

    death_text = SMALL.render(
        f"PEDESTRIAN COLLISIONS: {people_died}",
        True, (255, 130, 120)
    )

    screen.blit(death_text, (15, 61))

    controls = SMALL.render(
        "WASD MOVE | SHIFT RUN | SPACE JUMP | V CAMERA | "
        "E ENTER | F SHOUT | N DAY/NIGHT | TAB MOUSE | R RESET",
        True, (220, 220, 220)
    )

    screen.blit(controls, (15, h - 120))


def draw_mobile_controls():
    if not mobile:
        return

    w, h = screen.get_size()

    buttons = [
        ("W", (70, h - 220, 55, 55)),
        ("A", (15, h - 165, 55, 55)),
        ("S", (70, h - 165, 55, 55)),
        ("D", (125, h - 165, 55, 55)),
        ("JUMP", (w - 115, h - 180, 90, 55)),
        ("E", (w - 115, h - 120, 90, 45)),
        ("F", (w - 115, h - 65, 90, 45)),
        ("V", (w - 220, h - 65, 90, 45))
    ]

    for text, rect in buttons:
        pygame.draw.rect(screen, (40, 40, 45), rect, border_radius=12)
        pygame.draw.rect(screen, (170, 170, 170), rect, 2, border_radius=12)

        image = SMALL.render(text, True, (255, 255, 255))
        screen.blit(
            image,
            (rect[0] + rect[2] / 2 - image.get_width() / 2,
             rect[1] + rect[3] / 2 - image.get_height() / 2)
        )


def draw_death():
    w, h = screen.get_size()
    fade = int(clamp(death_timer * 80, 0, 255))

    overlay = pygame.Surface((w, h), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, fade))
    screen.blit(overlay, (0, 0))

    if death_timer > 2:
        title = BIG.render("YOU DIED", True, (230, 230, 230))
        subtitle = FONT.render("TON 618", True, (180, 180, 180))

        screen.blit(title, (w // 2 - title.get_width() // 2, h // 2 - 45))
        screen.blit(subtitle, (w // 2 - subtitle.get_width() // 2, h // 2 + 10))


def toggle_mouse():
    global locked
    locked = not locked
    pygame.event.set_grab(locked)
    pygame.mouse.set_visible(not locked)
    pygame.mouse.get_rel()


def reset():
    global player, yaw, pitch, vy, grounded
    global dead, death_timer, elapsed, inside, house, night
    global third_person, camera_smooth, people_died, collision_flash

    player.update(0, GROUND, -10)
    yaw = 0
    pitch = 0
    vy = 0
    grounded = True

    dead = False
    death_timer = 0
    elapsed = 0
    inside = False
    house = None
    night = True
    third_person = False
    people_died = 0
    collision_flash = 0

    camera_smooth.update(player.x, player.y, player.z)
    camera_cached.update(player.x, player.y, player.z)
    set_caption("A quiet evening in Punjab.", 8)

    generate_buildings()
    generate_people()
    generate_cars()
    generate_birds()
    generate_trees()
    generate_lamps()


def render(threat):
    if inside:
        draw_interior()
        draw_caption()
        draw_mobile_controls()
        return

    draw_sky()

    if not night:
        p = project((player.x - 100, player.y + 100, player.z + 800))

        if p:
            pygame.draw.circle(
                screen, (255, 230, 150),
                (int(p[0]), int(p[1])),
                int(clamp(500 / p[2], 5, 45))
            )

    draw_black_hole(threat)
    draw_road()

    for b in buildings:
        draw_building(b)

    draw_trees()
    draw_lamps()

    for car in cars:
        draw_car(car)

    draw_people()
    flush()

    draw_birds()
    draw_lens_distortion(threat)
    draw_hud(threat)
    draw_caption()
    draw_mobile_controls()


generate_buildings()
generate_people()
generate_cars()
generate_birds()
generate_trees()
generate_lamps()

camera_smooth.update(
    player.x,
    player.y + camera_height,
    player.z - camera_distance
)

while running:
    dt = min(clock.tick(60) / 1000, .04)
    elapsed += dt
    collision_flash = max(0, collision_flash - dt)

    update_camera(dt)
    w, h = screen.get_size()

    if w < 320 or h < 240:
        continue

    keys = pygame.key.get_pressed()
    threat = threat_level()
    remaining = black_hole_distance()

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        elif event.type == pygame.VIDEORESIZE:
            W, H = event.w, event.h
            screen = pygame.display.set_mode((W, H), pygame.RESIZABLE)

        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if locked:
                    toggle_mouse()
                else:
                    running = False

            elif event.key == pygame.K_TAB and not inside:
                toggle_mouse()

            elif event.key == pygame.K_v and not inside:
                third_person = not third_person
                camera_smooth.update(
                    player.x - math.sin(yaw) * camera_distance,
                    player.y + camera_height,
                    player.z - math.cos(yaw) * camera_distance
                )

            elif event.key == pygame.K_SPACE and grounded and not dead:
                vy = JUMP
                grounded = False

            elif event.key == pygame.K_f:
                alert_crowd()

            elif event.key == pygame.K_e:
                if inside:
                    leave_house()
                else:
                    enter_house()

            elif event.key == pygame.K_n:
                night = not night
                set_caption("Night falls." if night else "Morning arrives.", 5)

            elif event.key == pygame.K_l:
                low_detail = not low_detail

            elif event.key == pygame.K_r:
                reset()

        elif event.type == pygame.MOUSEMOTION:
            if locked and not dead and not inside:
                mx, my = event.rel
                yaw += mx * SENS
                pitch -= my * SENS
                pitch = clamp(pitch, -1.45, 1.45)

        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1 and not locked:
                toggle_mouse()

        elif event.type == pygame.MOUSEWHEEL:
            if third_person:
                camera_distance = clamp(camera_distance - event.y * .7, 3, 15)

        elif event.type == pygame.FINGERDOWN:
            mobile = True
            pos = (int(event.x * w), int(event.y * h))

            if pos[0] >= w * .4:
                touch_look = pos
            else:
                touch_move = pos

        elif event.type == pygame.FINGERMOTION:
            mobile = True
            pos = (int(event.x * w), int(event.y * h))

            if touch_look:
                dx = pos[0] - touch_look[0]
                dy = pos[1] - touch_look[1]

                yaw -= dx * .004
                pitch -= dy * .004
                pitch = clamp(pitch, -1.45, 1.45)
                touch_look = pos

            if touch_move:
                touch_move = pos

        elif event.type == pygame.FINGERUP:
            touch_look = None
            touch_move = None

    if not dead:
        if inside:
            update_interior(dt, threat)

        else:
            forward = pygame.Vector3(math.sin(yaw), 0, math.cos(yaw))
            right = pygame.Vector3(math.cos(yaw), 0, -math.sin(yaw))

            movement = pygame.Vector3()

            if keys[pygame.K_w]:
                movement += forward

            if keys[pygame.K_s]:
                movement -= forward

            if keys[pygame.K_a]:
                movement -= right

            if keys[pygame.K_d]:
                movement += right

            if touch_move:
                movement += forward

            if movement.length_squared():
                movement = movement.normalize() * (8 * dt)

                if keys[pygame.K_LSHIFT]:
                    movement *= 2

                move_player(movement.x, movement.z)

            if not grounded:
                vy -= GRAVITY * dt
                player.y += vy * dt

                if player.y <= GROUND:
                    player.y = GROUND
                    vy = 0
                    grounded = True

            update_people(dt)
            update_cars(dt, threat)
            check_car_collisions()
            update_birds(dt, threat)
            recycle_buildings()

            for p in people:
                if p["state"] == "dead":
                    continue

                if p["z"] < player.z - 100:
                    p["z"] = player.z + random.uniform(400, 1800)
                    p["x"] = random.choice([-1, 1]) * random.uniform(5, 9)
                    p["state"] = "normal"

    if remaining <= 1 and not dead:
        dead = True
        death_timer = 0
        set_caption("TON 618 consumes the world.", 100)

        for p in people:
            p["state"] = "dead"

        for p in interior_people:
            p["state"] = "dead"

    if dead:
        death_timer += dt

    caption_timer -= dt

    render(threat)

    if dead:
        draw_death()

    pygame.display.flip()


pygame.mouse.set_visible(True)
pygame.event.set_grab(False)
pygame.quit()
sys.exit()