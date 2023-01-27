from __future__ import annotations

import argparse
import time

import cv2
import numpy
import serial

from scripts.engine import all_match
from scripts.engine import any_match
from scripts.engine import always_matches
from scripts.engine import Color
from scripts.engine import do
from scripts.engine import get_text
from scripts.engine import getframe
from scripts.engine import match_px
from scripts.engine import match_text
from scripts.engine import Point
from scripts.engine import Press
from scripts.engine import require_tesseract
from scripts.engine import run
from scripts.engine import SERIAL_DEFAULT
from scripts.engine import Wait
from scripts.engine import Write

# Initial State: 
# IMPORTANT: Plese read all steps here to insure the script functions normally:
# 1) Have the parents you want in your party (you may have up to 6)
# 2) Make sure you have all sandwich recipes and that you have enough ingredients
# for sandwich 25.
# 3) Have your Flame Body / Magma Armor Pokemon in slot 1 of the box before the
# currently saved one
# 4) Have x number of boxes empty starting at the current one.
# 5) Have nicknames off and auto send to boxes
# 6) Save in front of Area Zero Gate (the rocky section outside)
# 7) Progress up to overworld.
# 8) IMPORTANT: to detect shinies, set the background color of boxes that will
# recieve shinies to BACKGROUND 15, or change the images in shiny_check_images.
# 9) Start script, including connecting to controller

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--serial', default=SERIAL_DEFAULT)
    parser.add_argument('--boxes', type=int, required=True)
    parser.add_argument('--silent', type=bool, default=False)
    parser.add_argument('--initial', type=str, default='INITIAL')
    args = parser.parse_args()

    require_tesseract()

    vid = cv2.VideoCapture(0)
    vid.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    vid.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    start_time = 0.0
    shiny = False
    box = 0
    check_box = 0
    column = 0
    egg_count = 0
    eggs = 5

    def set_start(vid: object, ser: object) -> None:
        nonlocal start_time
        start_time = time.monotonic()

    def increment_egg_count(vid: object, ser: object) -> None:
        nonlocal egg_count
        egg_count += 1
        print(f'DEBUG: You have {egg_count} eggs currently')

    def reset_egg_count(vid: object, ser: object) -> None:
        nonlocal egg_count
        egg_count = 0

    def restart_eggs(frame: object) -> bool:
        return time.monotonic() > start_time + 30 * 60 
     
    def set_shiny() -> None:
        nonlocal shiny
        shiny = True   

    def are_we_done(frame: object) -> bool:
        return egg_count >= args.boxes * 30

    def bye(vid: object, ser: object) -> None:
        do(# save the game, exit
            Press('B'), Wait(2),
            Press('R'), Wait(2),
            Press('A'), Wait(3),
            Press('A'), Wait(1),
            Press('H'))(vid, ser)
        raise SystemExit

    def eggs_done(frame: object) -> bool:
        return eggs == 0

    def egg_hatched(vid: object, ser: object) -> None:
        nonlocal eggs
        eggs -= 1

    def column_matches(frame: numpy.ndarray) -> bool:
        x = 372 + 84 * column
        return any_match(match_px(Point(y=169, x=x), Color(b=42, g=197, r=213)), match_px(Point(y=169, x=x), Color(b=0, g=223, r=255)))(frame)

    def multiselect_matches(frame: numpy.ndarray) -> bool:
        x = 300 + 84 * column
        return any_match(match_px(Point(y=133, x=x), Color(b=38, g=193, r=226)), match_px(Point(y=133, x=x), Color(b=0, g=223, r=255)))(frame)

    def column_done(vid: cv2.VideoCapture, ser: serial.Serial) -> None:
        nonlocal box, column, eggs
        eggs = 5
        if column == 5:
            column = 0
            box += 1
        else:
            column += 1

        print(f'box={box + 1} column={column + 1}')

    def box_done(frame: object) -> bool:
        return column == 0

    def get_box(vid: cv2.VideoCapture, ser: object) -> None:
        nonlocal box_name
        box_name = get_text(
            getframe(vid),
            Point(y=85, x=448),
            Point(y=114, x=708),
            invert=True,
        )

    def next_box_matches(frame: numpy.ndarray) -> bool:
        return not match_text(
            box_name,
            Point(y=85, x=448),
            Point(y=114, x=708),
            invert=True,
        )(frame)

    def move_to_column(vid: cv2.VideoCapture, ser: serial.Serial) -> None:
        for _ in range(column):
            do(Press('d'), Wait(.4))(vid, ser)

    def all_done(frame: object) -> bool:
        return box == args.boxes

    def reset_vars(vid: object, ser: object) -> None:
        nonlocal box, check_box, column, eggs, egg_count
        box = 0
        check_box = 0
        column = 0
        egg_count = 0
        eggs = 5
        print('DEBUG: REACHED RESTART')

    def check_shiny(vid: cv2.VideoCapture, ser: serial.Serial) -> None:
        nonlocal check_box

        def _detect_shiny() -> None:
            match_px(Point(y=78, x=1139), Color(b=248, g=250, r=255))

            frame = getframe(vid)
            # check for white pixel of shiny icon
            print(f'DEBUG: Shiny? -- {match_px(Point(y=78, x=1139), Color(b=253, g=255, r=255))(frame)}')
            if match_px(Point(y=78, x=1139), Color(b=253, g=255, r=255))(frame):
                set_shiny()
                # alarm
                if not args.silent:
                    do(Press('!'),
                    Wait(1),
                    Press('.'),
                    Wait(.5),
                    Press('!'),
                    Wait(1),
                    Press('.'),
                    Wait(.5),
                    Press('!'),
                    Wait(1),
                    Press('.'),
                    Wait(.5),
                    )(vid, ser)
                    print('DEBUG: *****SHINY DETECTED!*****')

        for direction in 'dadad':
            _detect_shiny()
            for _ in range(5):
                do(Press(direction), Wait(.25))(vid, ser)
                _detect_shiny()
            do(Press('s'), Wait(.25))(vid, ser)

        for _ in range(2):
            do(Press('s'), Wait(.25))(vid, ser)
        for _ in range(5):
            do(Press('a'), Wait(.25))(vid, ser)

        do(Press('R'), Wait(.25))(vid, ser)
        check_box += 1

    def check_done(frame: object) -> bool:
        return check_box == args.boxes

    def check_done_w_shiny(frame: object) -> bool:
        return shiny and (check_box == args.boxes)

    def initialize_shiny_check(vid: object, ser: object) -> None:
        do(Wait(1), Press('A'), Wait(3))(vid, ser)
        if args.boxes > 1:
            for _ in range(args.boxes - 1):
                do(Press('L'), Wait(.5))(vid, ser)
        do(# action to make sure wallpaper shows up
        Press('A'), Wait(1), Press('A'), Wait(1), Press('A'), Wait(1))(vid, ser)

    select = do(
        Press('-'), Wait(.5), Press('s', duration=.8), Wait(.4),
        Press('A'), Wait(.5),
    )

    box_name = 'unknown'
    world_matches = any_match(match_px(Point(y=598, x=1160), Color(b=17, g=203, r=244)),match_px(Point(y=598, x=1160), Color(b=0, g=205, r=255)))
    boxes_matches = any_match(match_px(Point(y=241, x=1161), Color(b=28, g=183, r=209)),match_px(Point(y=234, x=1151), Color(b=0, g=204, r=255)))
    pos0_matches = any_match(match_px(Point(y=169, x=372), Color(b=42, g=197, r=213)), match_px(Point(y=169, x=372), Color(b=0, g=204, r=255)))
    pos1_matches = any_match(match_px(Point(y=251, x=366), Color(b=47, g=189, r=220)), match_px(Point(y=251, x=366), Color(b=0, g=204, r=255)))
    sel_text_matches = any_match(match_text(
        'Draw Selection Box',
        Point(y=679, x=762),
        Point(y=703, x=909),
        invert=True,
    ),
        match_text(
        'Draw Selection Box',
        Point(y=672, x=687),
        Point(y=710, x=831),
        invert=True,
    )
    )

    states = {
        'INITIAL': (
            (
                world_matches,
                do(
                    Wait(1),
                    # center camera
                    Press('L'), Wait(.1),
                    # open menu
                    Press('X'), Wait(1), Press('d'), Wait(1),
                ),
                'MENU',
            ),
        ),
        'MENU': (
            (
                any_match(
                    match_px(Point(y=292, x=1085), Color(b=30, g=185, r=210)),
                    match_px(Point(y=288, x=1027), Color(b=0, g=204, r=255)),
                ),
                do(
                    # press A on picnic menu
                    Wait(1), Press('A'), Wait(10),
                    # walk up to picnic
                    Press('w', duration=.5),
                    # sandwich time
                    Press('A'), Wait(1.5), Press('A'), Wait(5),
                ),
                'FIND_25',
            ),
            (always_matches, do(Press('s'), Wait(.5)), 'MENU'),
        ),
        'FIND_25': (
            (
                match_text(
                    '25',
                    Point(y=376, x=21),
                    Point(y=403, x=58),
                    invert=True,
                ),
                do(
                    # select sandwich
                    Press('A'), Wait(2),
                    # select pick
                    Press('A'), Wait(10),
                    # cheese 1
                    Press('w', duration=1),
                    Press('s', duration=.2),
                    Press('@', duration=.5),
                    Wait(1),
                    # cheese 2
                    Press('w', duration=1),
                    Press('s', duration=.2),
                    Press('@', duration=.5),
                    Wait(1),
                    # cheese 3
                    Press('w', duration=1),
                    Press('s', duration=.2),
                    Press('@', duration=.5),
                    Wait(3),
                    # bread
                    Press('A'), Wait(3),
                    # pick
                    Press('A'), Wait(10),
                    # confirm
                    Press('A'), Wait(25),
                    # noice
                    Press('A'), Wait(5),
                    # move around the table
                    Wait(.5),
                    Press('d', duration=.1), Wait(.2),
                    Press('L'), Wait(.2),
                    Press('w', duration=.4), Wait(.5),

                    Press('a', duration=.1), Wait(.2),
                    Press('L'), Wait(.2),
                    Press('w', duration=.7), Wait(.5),

                    Press('z', duration=.1), Wait(.2),
                    Press('L'), Wait(.2),
                    Press('w', duration=.5), Wait(.5),

                    Press('A'), Wait(1),
                ),
                'VERIFY_BASKET',
            ),
            (always_matches, do(Press('s'), Wait(1)), 'FIND_25'),
        ),
        'VERIFY_BASKET': (
            (
                match_text(
                    'You peeked inside the basket!',
                    Point(y=546, x=353),
                    Point(y=588, x=706),
                    invert=True,
                ),
                do(set_start, Wait(.1)),
                'MASH_A',
            ),
            (
                # if it fails, go back to the beginning
                always_matches,
                do(Press('B'), Wait(2), Press('Y'), Wait(.5), Press('A'), Wait(10),),
                'INITIAL',
            ),
        ),
        'MASH_A': (
            ( 
                match_text(
                    'You took the Egg!',
                    Point(y=540, x=351),
                    Point(y=640, x=909),
                    invert=True,
                ),
                do(increment_egg_count, Press('A'), Wait(1)),
                'MASH_A',
            ),
            (
                all_match(
                    match_px(Point(y=628, x=351), Color(b=49, g=43, r=30)),
                    match_px(Point(y=630, x=893), Color(b=49, g=43, r=30)),
                    match_px(Point(y=546, x=348), Color(b=49, g=43, r=30)),
                ),
                do(Press('A'), Wait(1)),
                'MASH_A',
            ),
            (always_matches, do(), 'WAIT'),
        ),
        'WAIT': (
            (
                # if we have either equal or more eggs than our boxes, go to hatching stage
                are_we_done,
                do(
                    reset_egg_count,
                    # exit picnic
                    Press('Y'), Wait(.5), Press('A'), Wait(10),
                    # open menu
                    Press('X'), Wait(1)
                ),
                'MENU_SWITCH',
            ),
            (
                # if the timer runs out, restart the egg grabbing sequence
                restart_eggs,
                do(Press('Y'), Wait(.5), Press('A'), Wait(10)),
                'INITIAL',
            ),
            (always_matches, do(Wait(30), Press('A'), Wait(.5)), 'MASH_A'),
        ),

        'MENU_SWITCH': (
            (
                any_match(
                    match_px(Point(y=241, x=1161), Color(b=28, g=183, r=209)),
                    match_px(Point(y=234, x=1151), Color(b=0, g=204, r=255)),
                ),
                do(
                    # press A on boxes
                    Wait(1), Press('A'), Wait(3),
                    # go back to previous box
                    Press('L'), Wait(.5),
                    # select mon
                    Press('A'), Wait(.5), Press('A'), Wait(.5),
                    # switch first mon
                    Press('a'), Wait(.5), Press('A'), Wait(.5),
                    Press('s'), Wait(.5),
                    # move second mon
                    select,
                    Press('d'), Wait(.5), Press('d'), Wait(.5), Press('w'), Wait(.5), Press('A'), Wait(.5),
                    # re-orient, exit menu
                    Press('a'), Wait(.5), Press('R'), Wait(.5), Press('B'), Wait(3), Press('B'), Wait(3),
                ),
                'INITIAL_HATCH',
            ),
            (always_matches, do(Press('s'), Wait(.5)), 'MENU_SWITCH'),

        ),
        # EGG HATCH
        'INITIAL_HATCH': (
            (world_matches, do(Press('X'), Wait(1)), 'INITIAL_HATCH'),
            (
                match_text(
                    'MAIN MENU',
                    Point(y=116, x=888),
                    Point(y=147, x=1030),
                    invert=True,
                ),
                do(),
                'MENU_MOVE_RIGHT',
            ),
        ),
        'MENU_MOVE_RIGHT': (
            (
                any_match(
                    match_px(Point(y=156, x=390), Color(b=31, g=190, r=216)),
                    match_px(Point(y=156, x=390),  Color(b=0, g=225, r=255)),
                )
                ,
                do(Press('d'), Wait(.5)),
                'MENU_MOVE_RIGHT',
            ),
            (always_matches, do(), 'MENU_FIND_BOXES'),
        ),
        'MENU_FIND_BOXES': (
            (boxes_matches, do(), 'ENTER_BOXES'),
            (always_matches, do(Press('s'), Wait(.5)), 'MENU_FIND_BOXES'),
        ),
        'ENTER_BOXES': (
            (boxes_matches, do(Press('A'), Wait(3)), 'ENTER_BOXES'),
            (always_matches, do(), 'PICKUP_TO_COLUMN'),
        ),
        # loop point
        'PICKUP_TO_COLUMN': (
            (column_matches, do(), 'PICKUP_MINUS'),
            (always_matches, do(Press('d'), Wait(.4)), 'PICKUP_TO_COLUMN'),
        ),
        'PICKUP_MINUS': (
            (sel_text_matches, do(Press('-'), Wait(.5)), 'PICKUP_MINUS'),
            (always_matches, Press('s', duration=1), 'PICKUP_SELECTION'),
        ),
        'PICKUP_SELECTION': (
            (multiselect_matches, do(Press('A'), Wait(1)), 'PICKUP_SELECTION'),
            (always_matches, do(), 'PICKUP_TO_0'),
        ),
        'PICKUP_TO_0': (
            (pos0_matches, do(), 'PICKUP_TO_1'),
            (always_matches, do(Press('a'), Wait(.5)), 'PICKUP_TO_0'),
        ),
        'PICKUP_TO_1': (
            (pos1_matches, do(), 'PICKUP_TO_PARTY'),
            (always_matches, do(Press('s'), Wait(.5)), 'PICKUP_TO_1'),
        ),
        'PICKUP_TO_PARTY': (
            (   
                any_match(
                    match_px(Point(y=255, x=248), Color(b=22, g=198, r=229)),
                    match_px(Point(y=255, x=248), Color(b=0, g=219, r=255)),
                ),
                do(),
                'PICKUP_DROP',
            ),
            (always_matches, do(Press('a'), Wait(.5)), 'PICKUP_TO_PARTY'),
        ),
        'PICKUP_DROP': (
            (sel_text_matches, do(), 'PICKUP_EXIT_BOX'),
            (always_matches, do(Press('A'), Wait(1)), 'PICKUP_DROP'),
        ),
        'PICKUP_EXIT_BOX': (
            (world_matches, do(), 'REORIENT_OPEN_MAP'),
            (always_matches, do(Press('B'), Wait(1)), 'PICKUP_EXIT_BOX'),
        ),
        'REORIENT_OPEN_MAP': (
            (world_matches, do(Press('Y'), Wait(5)), 'REORIENT_OPEN_MAP'),
            (always_matches, do(), 'REORIENT_FIND_ZERO'),
        ),
        'REORIENT_FIND_ZERO': (
            (
                match_text(
                    'Zero Gate',
                    Point(y=251, x=584),
                    Point(y=280, x=695),
                    invert=False,
                ),
                do(),
                'REORIENT_MASH_A',
            ),
            (
                always_matches,
                do(Press('$', duration=.11), Wait(1)),
                'REORIENT_FIND_ZERO',
            ),
        ),
        'REORIENT_MASH_A': (
            (
                match_text(
                    'Map',
                    Point(y=90, x=226),
                    Point(y=124, x=276),
                    invert=False,
                ),
                do(Press('A'), Wait(1)),
                'REORIENT_MASH_A',
            ),
            (always_matches, do(), 'REORIENT_MOVE'),
        ),
        'REORIENT_MOVE': (
            (
                world_matches,
                do(
                    Wait(1),
                    Press('+'), Wait(1),
                    Press('z'), Wait(.5), Press('L'), Wait(.5),
                    Press('w', duration=2.5),
                    Press('L'), Wait(.1),
                ),
                'HATCH_5',
            ),
        ),
        'HATCH_5': (
            (
                all_match(
                    match_px(Point(y=541, x=930), Color(b=49, g=43, r=30)),
                    match_text(
                        'Oh?',
                        Point(y=546, x=353),
                        Point(y=586, x=410),
                        invert=True,
                    ),
                ),
                do(Press('A'), Wait(15)),
                'HATCH_1',
            ),
            (eggs_done, Wait(3), 'DEPOSIT_MENU'),
            (always_matches, do(Write('#'), Wait(1)), 'HATCH_5'),
        ),
        'HATCH_1': (
            (
                match_px(Point(y=598, x=1160), Color(b=17, g=203, r=244)),
                egg_hatched,
                'HATCH_5',
            ),
            (always_matches, do(Press('A'), Wait(1)), 'HATCH_1'),
        ),
        'DEPOSIT_MENU': (
            (world_matches, do(Press('X'), Wait(1)), 'DEPOSIT_MENU'),
            (always_matches, do(), 'DEPOSIT_ENTER_BOXES'),
        ),
        'DEPOSIT_ENTER_BOXES': (
            (boxes_matches, do(Press('A'), Wait(3)), 'DEPOSIT_ENTER_BOXES'),
            (always_matches, do(), 'DEPOSIT_TO_1'),
        ),
        'DEPOSIT_TO_1': (
            (pos1_matches, do(), 'DEPOSIT_TO_PARTY'),
            (always_matches, do(Press('s'), Wait(.5)), 'DEPOSIT_TO_1'),
        ),
        'DEPOSIT_TO_PARTY': (
            (
                any_match(
                    match_px(Point(y=255, x=248), Color(b=22, g=198, r=229)),
                    match_px(Point(y=255, x=248), Color(b=0, g=219, r=255)),
                ),
                do(),
                'DEPOSIT_MINUS',
            ),
            (always_matches, do(Press('a'), Wait(.5)), 'DEPOSIT_TO_PARTY'),
        ),
        'DEPOSIT_MINUS': (
            (sel_text_matches, do(Press('-'), Wait(.5)), 'DEPOSIT_MINUS'),
            (always_matches, Press('s', duration=1), 'DEPOSIT_SELECTION'),
        ),
        'DEPOSIT_SELECTION': (
            (
                any_match(
                match_px(Point(y=217, x=27), Color(b=15, g=200, r=234)),
                match_px(Point(y=217, x=27), Color(b=0, g=219, r=255)),
            ),
                do(Press('A'), Wait(1)),
                'DEPOSIT_SELECTION',
            ),
            (always_matches, do(), 'DEPOSIT_BACK_TO_1'),
        ),
        'DEPOSIT_BACK_TO_1': (
            (pos1_matches, do(), 'DEPOSIT_BACK_TO_0'),
            (always_matches, do(Press('d'), Wait(.5)), 'DEPOSIT_BACK_TO_1'),
        ),
        'DEPOSIT_BACK_TO_0': (
            (pos0_matches, do(), 'DEPOSIT_TO_COLUMN'),
            (always_matches, do(Press('w'), Wait(.5)), 'DEPOSIT_BACK_TO_0'),
        ),
        'DEPOSIT_TO_COLUMN': (
            (column_matches, do(), 'DEPOSIT_DROP'),
            (always_matches, do(Press('d'), Wait(.5)), 'DEPOSIT_TO_COLUMN'),
        ),
        'DEPOSIT_DROP': (
            (sel_text_matches, column_done, 'DEPOSIT_NEXT'),
            (always_matches, do(Press('A'), Wait(1)), 'DEPOSIT_DROP'),
        ),
        'DEPOSIT_NEXT': (
            (all_done, do(Press('B'), Wait(2)), 'CHECK_SHINY_MENU'),
            (box_done, get_box, 'DEPOSIT_NEXT_BOX'),
            (always_matches, do(), 'PICKUP_TO_COLUMN'),
        ),
        'DEPOSIT_NEXT_BOX': (
            (next_box_matches, do(), 'PICKUP_TO_COLUMN'),
            (always_matches, do(Press('R'), Wait(1)), 'DEPOSIT_NEXT_BOX'),
        ),
        'CHECK_SHINY_MENU': (
            (
                boxes_matches,
                # press A on boxes menu
                initialize_shiny_check,
                'CHECK_SHINY',
            ),
            (always_matches, do(Press('s'), Wait(.75)), 'CHECK_SHINY_MENU'),
        ),
        'CHECK_SHINY': (
            (check_done_w_shiny, bye, 'EXIT'),
            (check_done, reset_vars, 'RESET_SEQUENCE'),
            (always_matches, check_shiny, 'RESET_TIMEOUT'),
        ),
        'RESET_TIMEOUT': (
            (always_matches, do(Wait(1)), 'CHECK_SHINY'),
        ),
        'RESET_SEQUENCE': (
            (
                # only restart the game if no shiny
                lambda frame: not shiny, 
                do(
                    # hard reset the game via home
                    Press('H'), Wait(1),
                    Press('X'), Wait(.5),
                    Press('A'), Wait(4),
                    # restart the game
                    Press('A'), Wait(2),
                    Press('A'), Wait(20),
                    Press('A'), Wait(22)
                ),
                'INITIAL'
            ),
            # catch all in case it enters this stage with a shiny detected
            (always_matches, bye, 'INVALID')
        )
    }

    with serial.Serial(args.serial, 9600) as ser:
        run(vid=vid, ser=ser, initial=args.initial, states=states)


if __name__ == '__main__':
    raise SystemExit(main())
