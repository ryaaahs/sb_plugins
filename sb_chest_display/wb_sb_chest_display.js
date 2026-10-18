/* ---- plugin: sb_chest_display ---------------------------------------------- */
/**
 * Plugin entry point, called by WebBreak once the runtime is ready.
 * @param {Object} sbpe - the WebBreak plugin API (PluginBase, util, refs, register, canvasFillRect ...)
 */
WebBreakPlugins.push(function sb_chest_display(sbpe) {
'use strict';
// port of ryaaahs/sb_plugins sb_chest_display.py: shows the loot of every
// closed chest in a box above it, coloured by modifier count, with optional
// remove/display filters, EC/UC and duplicate-item compression and
// "perf item" highlighting.
//
// install:
//   1. paste this whole block after the last WebBreakPlugins.push(...) block
//      (just above the "WebBreak runtime" banner)
//   2. add the config section and the keybind line shown at the end of this
//      block to WebBreakConfig, and put sb_chest_display last in [manager]
//      priority (or leave it out of the list: unlisted plugins run last)
//
// differences from the python plugin, all because of the browser:
//   - items.json / boosts.json are embedded below (no file access)
//   - filters are the JS arrays below; python literals (True/False/None) work,
//     so entries from item_groups/perf_items.txt paste in unchanged
//     (change its "#" comment lines to "//")
//   - the debug markers (DEBUG_MODE) were dropped
var util = sbpe.util;
var mem = WebBreak.mem;
var refs = sbpe.refs;

// layout px -> canvas px. When the boxes scale with the zoom the layout is in canvas
// pixels like the game's HUD (1), but never below scd_min_scale of their normal
// on-screen size so the text stays readable when zoomed far out; refs.scaleX/scaleY
// when they keep a fixed window size
var LAYOUT_SCALE = { x: 1, y: 1 };

// ---- sizes of the boxes, in layout pixels (same values as the python plugin) ----
var LABEL_HEIGHT = 22;                // one line of text
var LABEL_PADDING_X = 32;             // empty space left and right of a line's text
var LABEL_TEXT_OFFSET_Y = 5;          // text starts this far below the top of its line
var INDENT_PER_POSITION = 10;         // item name = position 0, modifier lines = position 1
var INDENT_PER_LEVEL = 5;             // extra indent of lines inside a panel group
var DIVIDER_HEIGHT = 4;               // space taken by the line between two items
var DIVIDER_INSET = 11;               // the line stops this far from the box edges
var DIVIDER_COLOUR = 0xFF808080;      // ARGB
var PANEL_HORIZONTAL_SPACING = 3;     // space left and right of the content in a box
var PANEL_VERTICAL_SPACING = 20;
var FONT_BASE_SIZE = 13;              // text size at layout scale 1
var MIN_FONT_SIZE = 6;

// ---- memory layout and caching ----
var SUBPIXELS_PER_PIXEL = 256;        // world positions are stored in 1/256 px
var POINTER_SIZE_BYTES = 4;           // wasm32
var MAX_REPEATED_FIELD_ELEMENTS = 1000;   // sanity limit when reading a RepeatedPtrField
var HASH_MULTIPLIER = 31;
var TEXT_CACHE_MAX_AGE_FRAMES = 180;      // unused text textures are destroyed after this
var TEXT_CACHE_PRUNE_INTERVAL_FRAMES = 120;

//@@USER-SETTINGS-BEGIN
// zones where nothing is shown
var IGNORED_ZONE = ['home', 'lobby'];

var True = true, False = false, None = null;

// You can only have one filter type at a time (remove wins if both are on).
// With scd_ec_uc_compress on, use {"name": "EC"} / {"name": "UC"} for currency;
// with it off use {"name": "1 EC"}, {"name": "5 EC"}, {"name": "10 EC"},
// {"name": "25 EC"}, {"name": "1 UC"}, {"name": "5 UC"}.
//   catch-all (any modifiers):  {"name": "Jansky Repeater"}
//   exact modifiers (case sensitive, names from boosts.json):
//     {"name": "Jansky Repeater", "modifiers": []}
//     {"name": "Jansky Repeater", "modifiers": ["Shots", "Precise"]}
// non-modified items must use the catch-all form.

// scd_remove_filter: hides the listed items (empty list = hide nothing)
var remove_filter_list = [
  // {"name": "Jansky Repeater"},
];

// scd_display_filter: shows only the listed items (empty list = show nothing)
var display_filter_list = [
  // {"name": "Jansky Repeater"},
];

// items to highlight as "<variant> <name>" (DPS / COMB / Range ...).
// filters apply to these too, so keep that in mind when writing them
var perf_tracking = [
  {"name": "Kantikoy Repeater", "variant": "Range", "tracking": True, "modifiers": ["Shots", "Armor Piercing"]},
];
//@@USER-SETTINGS-END

var ITEM_MODS = ['', 'Modified', 'Custom', 'Experimental', 'Prototype'];

// ---------------------------------------------------------------------------
// game data (item_groups/items.json, item_groups/boosts.json)
// ---------------------------------------------------------------------------
// id -> [name, class, slot]
var ITEM_DATA = {"31":["Kantikoy Repeater","Wildfire","Main"],"147":["Compound Repeater","Wildfire","Main"],"148":["Redshift Repeater","Wildfire","Main"],"149":["Tektite Repeater","Wildfire","Main"],"207":["Aerolith Repeater","Wildfire","Main"],"4":["Shotgun","Wildfire","Main"],"5":["Arblast","Wildfire","Main"],"150":["Dragoon","Wildfire","Main"],"208":["Bombard","Wildfire","Main"],"209":["Jansky Repeater","Wildfire","Main"],"108":["Soidal Repeater","Wildfire","Main"],"109":["Bolt Thrower","Wildfire","Main"],"56":["Ancient Gun","Wildfire","Main"],"65":["Ancient Super Gun","Wildfire","Main"],"2":["Frag","Wildfire","Secondary"],"38":["Improved Frag","Wildfire","Secondary"],"151":["Contrived Frag","Wildfire","Secondary"],"152":["Synthetic Frag","Wildfire","Secondary"],"153":["Reforged Frag","Wildfire","Secondary"],"210":["Unstable Frag","Wildfire","Secondary"],"39":["Cluster","Wildfire","Secondary"],"40":["Swarm Cluster","Wildfire","Secondary"],"212":["Hydra","Wildfire","Secondary"],"194":["Tripwire","Wildfire","Secondary"],"110":["Proxies","Wildfire","Secondary"],"57":["Ancient Grenade","Wildfire","Secondary"],"63":["Blast","Wildfire","Special"],"69":["Empowered Blast","Wildfire","Special"],"154":["Withering Blast","Wildfire","Special"],"155":["Voracious Blast","Wildfire","Special"],"156":["Zealous Blast","Wildfire","Special"],"213":["Furious Blast","Wildfire","Special"],"70":["Forceful Blast","Wildfire","Special"],"214":["Fireform","Wildfire","Special"],"71":["Scattered Blast","Wildfire","Special"],"14":["Jerkin","Wildfire","Body"],"55":["Durable Jerkin","Wildfire","Body"],"247":["Augmented Jerkin","Wildfire","Body"],"248":["Reinforced Jerkin","Wildfire","Body"],"249":["Resilient Jerkin","Wildfire","Body"],"261":["Talons","Wildfire","Mobility"],"262":["Durable Talons","Wildfire","Mobility"],"263":["Augmented Talons","Wildfire","Mobility"],"264":["Reinforced Talons","Wildfire","Mobility"],"265":["Resilient Talons","Wildfire","Mobility"],"9":["Skein","Duskwing","Main"],"35":["Nacre Skein","Duskwing","Main"],"157":["Cobalt Skein","Duskwing","Main"],"158":["Sapphire Skein","Duskwing","Main"],"159":["Berylblade Skein","Duskwing","Main"],"215":["Vitreous Skein","Duskwing","Main"],"46":["Polychrome Skein","Duskwing","Main"],"216":["Motley","Duskwing","Main"],"116":["Balefire Skein","Duskwing","Main"],"217":["Skyfire Skein","Duskwing","Main"],"117":["Baetyl","Duskwing","Main"],"1":["Aesc","Duskwing","Secondary"],"41":["Biting Aesc","Duskwing","Secondary"],"160":["Falcate Aesc","Duskwing","Secondary"],"161":["Keen Aesc","Duskwing","Secondary"],"162":["Violet Aesc","Duskwing","Secondary"],"218":["Radiant Aesc","Duskwing","Secondary"],"195":["Haunting Aesc","Duskwing","Secondary"],"72":["Gnawing Aesc","Duskwing","Secondary"],"111":["Kulbeda","Duskwing","Secondary"],"219":["Kunai","Duskwing","Main"],"10":["Warp","Duskwing","Special"],"42":["Acrotic Warp","Duskwing","Special"],"163":["Beloid Warp","Duskwing","Special"],"164":["Daedal Warp","Duskwing","Special"],"165":["Aeon Warp","Duskwing","Special"],"221":["Tacent Warp","Duskwing","Special"],"196":["Residual Warp","Duskwing","Special"],"98":["Abiding Warp","Duskwing","Special"],"112":["Mirrored Warp","Duskwing","Special"],"222":["Mimic","Duskwing","Special"],"250":["Augmented Hyrst","Duskwing","Body"],"251":["Reinforced Hyrst","Duskwing","Body"],"252":["Resilient Hyrst","Duskwing","Body"],"184":["Augmented Trackers","Duskwing","Mobility"],"259":["Reinforced Trackers","Duskwing","Mobility"],"260":["Resilient Trackers","Duskwing","Mobility"],"193":["Needlebow",["Wildfire","Duskwing"],"Main"],"144":["Stonebow",["Wildfire","Duskwing"],"Main"],"34":["Hyrst",["Wildfire","Duskwing"],"Body"],"103":["Durable Hyrst",["Wildfire","Duskwing"],"Body"],"15":["Trackers",["Wildfire","Duskwing"],"Mobility"],"258":["Durable Trackers",["Wildfire","Duskwing"],"Mobility"],"16":["Empyreals",["Wildfire","Duskwing"],"Mobility"],"266":["Aeonic Empyreals",["Wildfire","Duskwing"],"Mobility"],"188":["Bandolier",["Wildfire","Duskwing","Ironclad"],"Body"],"189":["Double Bandolier",["Wildfire","Duskwing","Ironclad"],"Body"],"190":["Berserker",["Wildfire","Duskwing","Ironclad"],"Body"],"256":["Frenzied Berserker",["Wildfire","Duskwing","Ironclad"],"Body"],"6":["Sledge","Ironclad","Main"],"36":["Cruel Sledge","Ironclad","Main"],"166":["Vengeful Sledge","Ironclad","Main"],"167":["Sinful Sledge","Ironclad","Main"],"168":["Baleful Sledge","Ironclad","Main"],"223":["Corrupt Sledge","Ironclad","Main"],"197":["Lancet","Ironclad","Main"],"119":["Baculus","Ironclad","Main"],"47":["Adjudicator","Ironclad","Main"],"224":["Quaestor","Ironclad","Main"],"118":["Preceptor","Ironclad","Main"],"7":["Kyeser","Ironclad","Secondary"],"44":["Irascent Kyeser","Ironclad","Secondary"],"169":["Caustic Kyeser","Ironclad","Secondary"],"170":["Insidious Kyeser","Ironclad","Secondary"],"171":["Nefarious Kyeser","Ironclad","Secondary"],"226":["Diabolical Kyeser","Ironclad","Secondary"],"198":["Hotfoot","Ironclad","Secondary"],"115":["Burner","Ironclad","Secondary"],"45":["Swarmer","Ironclad","Secondary"],"312":["Triad","Ironclad","Secondary"],"227":["Locust","Ironclad","Secondary"],"11":["Mantlet","Ironclad","Special"],"32":["Relentless Mantlet","Ironclad","Special"],"172":["Fortified Mantlet","Ironclad","Special"],"173":["Banded Mantlet","Ironclad","Special"],"174":["Annealed Mantlet","Ironclad","Special"],"228":["Eternal Mantlet","Ironclad","Special"],"33":["Plating","Ironclad","Body"],"102":["Durable Plating","Ironclad","Body"],"244":["Augmented Plating","Ironclad","Body"],"245":["Reinforced Plating","Ironclad","Body"],"246":["Resilient Plating","Ironclad","Body"],"43":["Sabatons","Ironclad","Mobility"],"267":["Durable Sabatons","Ironclad","Mobility"],"185":["Augmented Sabatons","Ironclad","Mobility"],"268":["Reinforced Sabatons","Ironclad","Mobility"],"269":["Resilient Sabatons","Ironclad","Mobility"],"187":["Stompers","Ironclad","Mobility"],"270":["Spiked Stompers","Ironclad","Mobility"],"53":["Dancer","Fabricator","Main"],"58":["Deepfire Dancer","Fabricator","Main"],"175":["Everdawn Dancer","Fabricator","Main"],"176":["Fellwhip Dancer","Fabricator","Main"],"177":["Darkstar Dancer","Fabricator","Main"],"229":["Direfall Dancer","Fabricator","Main"],"199":["Telson","Fabricator","Main"],"113":["Gavotte","Fabricator","Main"],"66":["Trinity","Fabricator","Main"],"230":["Volta","Fabricator","Main"],"114":["Quickstep","Fabricator","Main"],"54":["Antiphon","Fabricator","Secondary"],"59":["Defiant Antiphon","Fabricator","Secondary"],"178":["Invidious Antiphon","Fabricator","Secondary"],"179":["Mocking Antiphon","Fabricator","Secondary"],"180":["Profane Antiphon","Fabricator","Secondary"],"232":["Blasphemous Antiphon","Fabricator","Secondary"],"200":["Mangonel","Fabricator","Secondary"],"233":["Scorpion","Fabricator","Secondary"],"67":["Whispered Antiphon","Fabricator","Secondary"],"311":["Silent Antiphon","Fabricator","Secondary"],"12":["Macron","Fabricator","Special"],"48":["Protracted Macron","Fabricator","Special"],"181":["Recalcitant Macron","Fabricator","Special"],"182":["Inveterate Macron","Fabricator","Special"],"183":["Composite Macron","Fabricator","Special"],"234":["Devoted Macron","Fabricator","Special"],"68":["Mechanized Macron","Fabricator","Special"],"235":["Skiff","Fabricator","Special"],"305":["Blink","Fabricator","Special"],"60":["Woven","Fabricator","Body"],"104":["Durable Woven","Fabricator","Body"],"253":["Augmented Woven","Fabricator","Body"],"254":["Reinforced Woven","Fabricator","Body"],"255":["Resilient Woven","Fabricator","Body"],"191":["Blockers","Fabricator","Body"],"192":["Enraged Blockers","Fabricator","Body"],"257":["Enlarged Blockers","Fabricator","Body"],"61":["Valenki","Fabricator","Mobility"],"271":["Durable Valenki","Fabricator","Mobility"],"186":["Augmented Valenki","Fabricator","Mobility"],"272":["Reinforced Valenki","Fabricator","Mobility"],"273":["Resilient Valenki","Fabricator","Mobility"],"146":["Lightfoot","Fabricator","Mobility"],"277":["Boosters",["Ironclad","Fabricator"],"Mobility"],"274":["Overloaded Boosters",["Ironclad","Fabricator"],"Mobility"],"105":["Gliders",["Ironclad","Fabricator"],"Mobility"],"106":["Volatile Gliders",["Ironclad","Fabricator"],"Mobility"],"62":["Teleport Throw","Toaster","Special"],"64":["Star","Toaster","Secondary"],"18":["Health Boost 1","Miscellaneous","NA"],"21":["Ammo Boost","Miscellaneous","NA"],"49":["1 EC","Miscellaneous","NA"],"96":["5 EC","Miscellaneous","NA"],"50":["10 EC","Miscellaneous","NA"],"97":["25 EC","Miscellaneous","NA"],"291":["1 UC","Miscellaneous","NA"],"292":["5 UC","Miscellaneous","NA"],"51":["Implant Slot 1","Miscellaneous","NA"],"19":["Max Health Boost 1","Miscellaneous","NA"],"20":["Max Health Boost 2","Miscellaneous","NA"],"92":["Max Health Boost 3","Miscellaneous","NA"],"93":["Max Health Boost 4","Miscellaneous","NA"],"236":["Max Health Boost 5","Miscellaneous","NA"],"22":["Max Ammo Boost 1","Miscellaneous","NA"],"23":["Max Ammo Boost 2","Miscellaneous","NA"],"94":["Max Ammo Boost 3","Miscellaneous","NA"],"95":["Max Ammo Boost 4","Miscellaneous","NA"],"237":["Max Ammo Boost 5","Miscellaneous","NA"],"120":["Armor Boost 1","Miscellaneous","NA"],"121":["Armor Boost 2","Miscellaneous","NA"],"122":["Armor Boost 3","Miscellaneous","NA"],"123":["Armor Boost 4","Miscellaneous","NA"],"238":["Armor Boost 5","Miscellaneous","NA"],"124":["Movement Speed Boost 1","Miscellaneous","NA"],"125":["Movement Speed Boost 2","Miscellaneous","NA"],"126":["Movement Speed Boost 3","Miscellaneous","NA"],"127":["Movement Speed Boost 4","Miscellaneous","NA"],"239":["Movement Speed Boost 5","Miscellaneous","NA"],"128":["Jump Height Boost 1","Miscellaneous","NA"],"129":["Jump Height Boost 2","Miscellaneous","NA"],"130":["Jump Height Boost 3","Miscellaneous","NA"],"131":["Jump Height Boost 4","Miscellaneous","NA"],"240":["Jump Height Boost 5","Miscellaneous","NA"],"132":["Damage Boost 1","Miscellaneous","NA"],"133":["Damage Boost 2","Miscellaneous","NA"],"134":["Damage Boost 3","Miscellaneous","NA"],"135":["Damage Boost 4","Miscellaneous","NA"],"241":["Damage Boost 5","Miscellaneous","NA"],"136":["Crit Chance Boost 1","Miscellaneous","NA"],"137":["Crit Chance Boost 2","Miscellaneous","NA"],"138":["Crit Chance Boost 3","Miscellaneous","NA"],"139":["Crit Chance Boost 4","Miscellaneous","NA"],"242":["Crit Chance Boost 5","Miscellaneous","NA"],"140":["Crit Damage Boost 1","Miscellaneous","NA"],"141":["Crit Damage Boost 2","Miscellaneous","NA"],"142":["Crit Damage Boost 3","Miscellaneous","NA"],"143":["Crit Damage Boost 4","Miscellaneous","NA"],"243":["Crit Damage Boost 5","Miscellaneous","NA"],"99":["Fungus Cave Key","Miscellaneous","NA"],"201":["Vanquished Key","Miscellaneous","NA"],"100":["Underground Base Key","Miscellaneous","NA"],"107":["Strands Key","Miscellaneous","NA"],"101":["Graveyard Key","Miscellaneous","NA"],"145":["Temple of the Lost Key","Miscellaneous","NA"],"205":["Unknown Key","Miscellaneous","NA"],"206":["Mysterious Key","Miscellaneous","NA"],"73":["Inferior Bellites","Any","Implant"],"74":["Bellites","Any","Implant"],"76":["Inferior Salites","Any","Implant"],"77":["Salites","Any","Implant"],"79":["Inferior Delites","Any","Implant"],"80":["Delites","Any","Implant"],"82":["Inferior Calites","Any","Implant"],"83":["Calites","Any","Implant"],"85":["Inferior Armites","Any","Implant"],"86":["Armites","Any","Implant"],"88":["Exites","Any","Implant"],"89":["Inferior Emites","Any","Implant"],"90":["Emites","Any","Implant"],"299":["Inferior Velites","Any","Implant"],"300":["Velites","Any","Implant"],"302":["Inferior Firites","Any","Implant"],"303":["Firites","Any","Implant"],"308":["Inferior Ultrites","Any","Implant"],"309":["Ultrites","Any","Implant"]};
// [id, name, display_type, divide_value, class, slot]
var BOOSTS = [[55,"Quick Shot",0,0,"Wildfire","Main"],[55,"Quick Summon",0,0,"Fabricator","Secondary"],[48,"Trisected",0,0,["Ironclad","Wildfire"],["Secondary","Special"]],[4,"Max Ammo",1,0,["Wildfire","Duskwing","Ironclad"],["Secondary","Body"]],[35,"Incendiary",0,0,["Wildfire","Fabricator"],["Secondary","Special"]],[33,"Bounce",1,0,["Wildfire","Duskwing"],["Main","Secondary"]],[36,"Shots",1,0,"Wildfire","Main"],[36,"Plinks",1,0,"Ironclad","Main"],[36,"Height",1,0,"Ironclad","Main"],[36,"Missiles",1,0,"Ironclad","Secondary"],[36,"Bombs",1,0,"Wildfire","Secondary"],[36,"Blasts",1,0,"Wildfire","Special"],[36,"Blockers",1,0,"Fabricator",["Secondary","Body"]],[36,"Dances",1,0,"Fabricator","Main"],[34,"Explosive Ammo",0,0,"Wildfire","Main"],[18,"Damage",2,0,["Wildfire","Duskwing","Ironclad"],["Mobility","Body"]],[20,"Base Crit Damage",3,1,["Wildfire","Duskwing","Fabricator"],["Mobility","Body"]],[12,"Jump Height",1,0,["Wildfire","Duskwing","Ironclad","Fabricator"],"Mobility"],[10,"Armor",1,0,["Wildfire","Duskwing","Ironclad","Fabricator"],["Mobility","Body"]],[11,"Movement Speed",1,0,["Wildfire","Duskwing","Ironclad","Fabricator"],["Mobility","Body"]],[21,"Air Blasts",1,0,"Wildfire","Special"],[21,"Air Warps",1,0,"Duskwing","Special"],[13,"Range",1,0,["Wildfire","Duskwing","Fabricator"],["Main","Secondary"]],[39,"Seeking",0,0,["Ironclad","Fabricator"],["Main","Secondary"]],[14,"Precise",0,0,"Wildfire","Main"],[32,"Penetrating",0,0,["Wildfire","Duskwing","Ironclad","Fabricator"],["Main","Secondary"]],[37,"Speed",1,0,["Duskwing","Ironclad"],["Main","Secondary","Special"]],[22,"Knockback Resist",2,0,"Ironclad",["Main","Special"]],[51,"Extra Hit",1,0,["Duskwing","Ironclad"],"Main"],[24,"Crit Chance",2,1,["Duskwing","Ironclad","Fabricator"],["Main","Secondary","Special"]],[23,"Base Crit Chance",2,1,["Wildfire","Duskwing","Fabricator"],["Mobility","Body"]],[43,"Armor Piercing",0,0,["Wildfire","Duskwing","Ironclad","Fabricator"],["Main","Secondary","Special"]],[57,"Cycle Time",4,0,"Fabricator","Main"],[57,"Cooldown",4,0,"Fabricator","Secondary"],[25,"Crit Damage",3,1,["Wildfire","Duskwing","Ironclad","Fabricator"],["Main","Special"]],[42,"Acceleration",1,0,"Ironclad",["Secondary","Special"]],[54,"Armored",0,0,"Fabricator","Secondary"],[38,"Duration",1,0,"Fabricator",["Main","Special"]],[38,"Lifetime",1,0,["Duskwing","Ironclad","Fabricator"],["Main","Secondary","Special"]],[56,"Shielded",0,0,"Fabricator","Special"],[53,"Spin Time",1,0,"Duskwing","Main"],[52,"Reflect",0,0,"Ironclad","Special"],[50,"Leech",5,0,"Duskwing","Main"],[47,"Barbed",0,0,"Wildfire","Secondary"],[45,"Simultaneous",1,0,["Duskwing","Ironclad","Fabricator"],["Main","Secondary","Special"]],[46,"Shrapnel",1,0,"Fabricator","Special"],[46,"Burns",1,0,"Ironclad","Secondary"],[49,"Gravity",6,0,"Fabricator","Mobility"]].map(function (boost_row) {
  return {
    id: boost_row[0], name: boost_row[1], display_type: boost_row[2],
    divide_value: boost_row[3], class: boost_row[4], slot: boost_row[5]
  };
});
var NULL_BOOST = { id: -1, name: 'NULL', display_type: 0, divide_value: 0, class: ['NULL'], slot: ['NULL'] };

var warned_keys = new Set();
/**
 * Logs a console warning the first time a given key is seen, so per-frame problems don't spam the console.
 * @param {string} key - identifies the problem; repeated keys are ignored
 * @param {string} message - warning text
 */
function warnOnce(key, message) {
  if (warned_keys.has(key)) return;
  warned_keys.add(key);
  console.warn('[WebBreak] sb_chest_display: ' + message);
}

/**
 * Looks up an item in the embedded items.json data.
 * @param {number} item_id
 * @returns {{name: string, class: (string|string[]), slot: string}} the item, or a placeholder (and a one-time warning) if the id is unknown
 */
function itemInfo(item_id) {
  var item_record = ITEM_DATA[item_id];
  if (!item_record) {
    warnOnce('item' + item_id, 'unknown item id ' + item_id + ' (not in items.json)');
    return { name: 'Unknown item ' + item_id, class: '?', slot: '?' };
  }
  return { name: item_record[0], class: item_record[1], slot: item_record[2] };
}

/**
 * Python's `value in collection`: membership for arrays, substring for strings.
 * @param {(string[]|string)} collection
 * @param {string} value
 * @returns {boolean} false when collection is neither an array nor a string
 */
function contains(collection, value) {
  if (Array.isArray(collection)) return collection.indexOf(value) !== -1;
  if (typeof collection === 'string') return collection.indexOf(value) !== -1;
  return false;
}

/**
 * Python's `Counter(a) == Counter(b)`: same elements with the same counts, in any order.
 * @param {Array} first_list
 * @param {Array} second_list
 * @returns {boolean}
 */
function sameBag(first_list, second_list) {
  if (first_list.length !== second_list.length) return false;
  var remaining_counts = new Map();
  first_list.forEach(function (element) {
    remaining_counts.set(element, (remaining_counts.get(element) || 0) + 1);
  });
  for (var index = 0; index < second_list.length; index++) {
    var remaining = remaining_counts.get(second_list[index]);
    if (!remaining) return false;
    remaining_counts.set(second_list[index], remaining - 1);
  }
  return true;
}

/**
 * Formats a number the way Python's str(float) does, so whole numbers keep a ".0" (2 -> "2.0").
 * @param {number} number
 * @returns {string}
 */
function pyFloat(number) { return Number.isInteger(number) ? number.toFixed(1) : String(number); }

/**
 * Parses a currency item name such as "25 EC" or "5 UC".
 * @param {string} item_name
 * @returns {?{kind: string, amount: number}} kind is "EC" or "UC"; null for any other item
 */
function currencyOf(item_name) {
  var match = /^(\d+) (EC|UC)$/.exec(item_name);
  return match ? { kind: match[2], amount: parseInt(match[1], 10) } : null;
}

/**
 * Finds the boost in boosts.json that matches an id and a set of filters.
 * Keys "class" and "slot" use Python's `in` semantics (substring for strings, membership for lists, any-of when the filter value is a list); any other key must be equal.
 * @param {number} boost_id - StatBoost.stat
 * @param {Object} filters - e.g. {class, slot} or {name, class, slot}
 * @returns {Object} the boost entry, or NULL_BOOST (with a one-time warning) when nothing matches
 */
function filterBoost(boost_id, filters) {
  for (var boost_index = 0; boost_index < BOOSTS.length; boost_index++) {
    var boost = BOOSTS[boost_index];
    if (boost.id !== boost_id) continue;
    var is_match = true;
    for (var filter_key in filters) {
      var filter_value = filters[filter_key];
      if (filter_key === 'slot' || filter_key === 'class') {
        if (Array.isArray(filter_value)) {
          if (!filter_value.some(function (candidate) { return contains(boost[filter_key], candidate); })) { is_match = false; break; }
        } else if (!contains(boost[filter_key], filter_value)) { is_match = false; break; }
      } else if (!(filter_key in boost) || boost[filter_key] !== filter_value) { is_match = false; break; }
    }
    if (is_match) return boost;
  }
  warnOnce('boost' + boost_id + JSON.stringify(filters),
           'no boost match, report to the plugin developer: boost id ' + boost_id +
           ', filters ' + JSON.stringify(filters));
  return NULL_BOOST;
}

// StatBoost -> display text and colours -------------------------------------

/**
 * Builds the display text of one stat boost, e.g. "Knockback Resist: +50%".
 * Handles the two ids that need the value to pick the right boost (43: Armor Piercing/Barbed, 36 on Ironclad main-slot items: Height/Plinks).
 * @param {{name: string, class: (string|string[]), slot: string}} item_data - the item the boost is on
 * @param {{stat: number, val: number}} boost
 * @returns {string}
 */
function boostText(item_data, boost) {
  var matched_boost, display_text = '';
  var class_and_slot_filters = { class: item_data.class, slot: item_data.slot };
  if (boost.stat === 43) {
    // armor piercing is stored as a value of 100, barbed as anything else
    matched_boost = filterBoost(boost.stat, { name: boost.val === 100 ? 'Armor Piercing' : 'Barbed',
                                              class: item_data.class, slot: item_data.slot });
  } else if (item_data.class === 'Ironclad' && item_data.slot === 'Main' && boost.stat === 36) {
    // two different boosts share this id, the value tells them apart
    var ironclad_boost_name = boost.val === 1 ? 'Height' : boost.val === 2 ? 'Plinks' : null;
    matched_boost = filterBoost(boost.stat, ironclad_boost_name
      ? { name: ironclad_boost_name, class: item_data.class, slot: item_data.slot }
      : class_and_slot_filters);
  } else {
    matched_boost = filterBoost(boost.stat, class_and_slot_filters);
  }
  display_text += matched_boost.name;

  var boost_value = boost.val;
  switch (matched_boost.display_type) {
    case 1: display_text += ': +' + boost_value; break;                                   // flat bonus
    case 2: display_text += ': +' + (matched_boost.divide_value === 1 ? pyFloat(boost_value / 100) : boost_value) + '%'; break;  // percent
    case 3: display_text += ': +' + (matched_boost.divide_value === 1 ? pyFloat(boost_value / 100) : boost_value) + 'x'; break;  // multiplier
    case 4: display_text += ': ' + boost_value; break;                                    // plain value
    case 5: display_text += ': +' + boost_value + 'HP'; break;                            // health
    case 6: display_text += ': -' + boost_value + '%'; break;                             // penalty percent
  }
  return display_text;
}

/**
 * Creates a plain display entry (no modifiers), used for the EC/UC totals.
 * @param {Object} config - the plugin config
 * @param {string} label_text - the label text
 * @returns {{item: Object, boosts: Array}} an entry in the same shape computeChest produces
 */
function addPlainToLoggingDisplay(config, label_text) {
  return {
    item: { text: label_text, amount: 1, size: config.scd_text_display_size, label_colour: 'ffffff', label_opacity: 255 },
    boosts: []
  };
}

/**
 * Creates the display entry of one item: its label plus one line per modifier, with colours picked by modifier count (or the perf item colours).
 * @param {Object} config - the plugin config
 * @param {{name: string, class: (string|string[]), slot: string}} item_data - the item data
 * @param {string} display_name - the label to show (already prefixed with Modified/Custom/... or the perf variant)
 * @param {{stat: number, val: number}[]} boosts - the item's modifiers
 * @param {boolean} is_perf_item - true when the item matched perf_tracking
 * @returns {{item: Object, boosts: Object[]}}
 */
function addItemToLoggingDisplay(config, item_data, display_name, boosts, is_perf_item) {
  var label_colour = 'ffffff', label_opacity = 255;
  var boost_colour = 'ffffff', boost_opacity = 255;
  var fill_background = 'ffffff', fill_background_opacity = 255;
  var modifier_count = boosts.length;

  var colour_tier = null;   // which colour set of the config is used
  if (is_perf_item) colour_tier = 'perf_item';
  else if (modifier_count === 1) colour_tier = 'modified';
  else if (modifier_count === 2) colour_tier = 'custom';
  else if (modifier_count === 3) colour_tier = 'experimental';
  else if (modifier_count === 4) colour_tier = 'prototype';
  if (colour_tier) {
    label_colour = config['scd_text_' + colour_tier + '_label_colour'];
    label_opacity = config['scd_text_' + colour_tier + '_label_colour_opacity'];
    boost_colour = config['scd_text_' + colour_tier + '_modifier_colour'];
    boost_opacity = config['scd_text_' + colour_tier + '_modifier_colour_opacity'];
    fill_background = config['scd_' + colour_tier + '_fill_background_colour'];
    fill_background_opacity = config['scd_' + colour_tier + '_fill_background_colour_opacity'];
  }

  var boost_display_entries = boosts.map(function (boost) {
    return { size: config.scd_text_display_size, text: boostText(item_data, boost), colour: boost_colour, opacity: boost_opacity };
  });

  return {
    item: {
      text: display_name, size: config.scd_text_display_size, amount: 1,
      label_colour: label_colour, label_opacity: label_opacity,
      fill_background: fill_background, fill_background_opacity: fill_background_opacity
    },
    boosts: boost_display_entries
  };
}

// ---------------------------------------------------------------------------
// reading chests out of game memory
// ---------------------------------------------------------------------------

/**
 * Reads a protobuf RepeatedPtrField as an array of struct views.
 * @param {Object} repeated_field - a RepeatedPtrField view (elements pointer + current_size)
 * @param {string} struct_name - struct name each element points to, e.g. "ItemProperties"
 * @returns {Object[]} views; empty when the field is empty or looks corrupt
 */
function ptrList(repeated_field, struct_name) {
  var element_count = repeated_field.current_size;
  var pointer_array_address = repeated_field.elements;
  var views = [];
  if (!pointer_array_address || element_count <= 0 || element_count > MAX_REPEATED_FIELD_ELEMENTS) return views;
  for (var index = 0; index < element_count; index++) {
    var element_address = mem.u32(pointer_array_address + index * POINTER_SIZE_BYTES);
    if (element_address) views.push(mem.cast(struct_name, element_address));
  }
  return views;
}

// ItemProperties.type can't be read as item_properties.type: every struct view has
// its own `type` property (the struct name) and the view builder skips fields with a
// clashing name, so read the int32 by offset
var ITEM_TYPE_OFFSET = null;
/**
 * Reads ItemProperties.type by offset. It can't be read as `it.type`: every struct view has its own `type` property (the struct name) and the view builder skips fields with a clashing name.
 * @param {Object} item_properties - an ItemProperties view
 * @returns {number} the item id
 */
function itemTypeOf(item_properties) {
  if (ITEM_TYPE_OFFSET === null) ITEM_TYPE_OFFSET = WebBreak.layout.ItemProperties[1].type[0];
  return mem.i32(item_properties.address + ITEM_TYPE_OFFSET);
}

/**
 * Copies a chest's loot out of game memory into plain objects, so the rest of the plugin never touches memory.
 * @param {Object} chest - a Chest view
 * @returns {{type: number, boosts: {stat: number, val: number}[]}[]}
 */
function readChestItems(chest) {
  return ptrList(chest.items, 'ItemProperties').map(function (item_properties) {
    return {
      type: itemTypeOf(item_properties),
      boosts: ptrList(item_properties.statboosts, 'StatBoost').map(function (stat_boost) {
        return { stat: stat_boost.stat >>> 0, val: stat_boost.val };
      })
    };
  });
}

/**
 * Cheap fingerprint of a chest's loot, used to notice when its contents change.
 * @param {{type: number, boosts: {stat: number, val: number}[]}[]} chest_items
 * @returns {number} 32-bit hash
 */
function hashEntries(chest_items) {
  var hash = chest_items.length | 0;
  for (var item_index = 0; item_index < chest_items.length; item_index++) {
    var chest_item = chest_items[item_index];
    hash = (Math.imul(hash, HASH_MULTIPLIER) + chest_item.type) | 0;
    for (var boost_index = 0; boost_index < chest_item.boosts.length; boost_index++) {
      hash = (Math.imul(hash, HASH_MULTIPLIER) + chest_item.boosts[boost_index].stat) | 0;
      hash = (Math.imul(hash, HASH_MULTIPLIER) + chest_item.boosts[boost_index].val) | 0;
    }
    hash = (Math.imul(hash, HASH_MULTIPLIER) + 7) | 0;   // separator between items
  }
  return hash;
}

/**
 * Gets the current zone name from the world properties, falling back to the music name when the zone is empty.
 * @param {Object} props - ClientWorld props view
 * @returns {string}
 */
function zoneName(props) {
  var zone = props.zone ? util.getstr(props.zone) : '';
  if (!zone) zone = props.music ? util.getstr(props.music) : '';
  return zone;
}

/**
 * Converts a world object's position to layout pixels (see LAYOUT_SCALE): the horizontal centre and the top edge.
 * World positions are in 1/256 px, and the width is halved to get from the left edge to the centre.
 * @param {{xmp: number, ymp: number, wmp: number}} object_props - Properties view of the object
 * @param {{x: number, y: number}} camera_offset - WorldView offset, in canvas px
 * @param {number} scale_x - layout px -> canvas px, horizontally
 * @param {number} scale_y - layout px -> canvas px, vertically
 * @returns {{x: number, y: number}}
 */
function toLayoutPosition(object_props, camera_offset, scale_x, scale_y) {
  // positions are in 1/256 px, widths in 1/256 px too (half of it is the centre)
  var centre_x = Math.floor(object_props.xmp / SUBPIXELS_PER_PIXEL) +
                 Math.floor(object_props.wmp / (SUBPIXELS_PER_PIXEL * 2));
  var top_y = Math.floor(object_props.ymp / SUBPIXELS_PER_PIXEL);
  return {
    x: Math.round((centre_x - camera_offset.x) / scale_x),
    y: Math.round((top_y - camera_offset.y) / scale_y)
  };
}

// ---------------------------------------------------------------------------
// drawing helpers (layout pixels, see LAYOUT_SCALE: canvas pixels when the boxes
// scale with the zoom, window pixels otherwise, like the python XDL_* calls with
// the canvas size swapped to the window size)
// ---------------------------------------------------------------------------

/**
 * Combines a hex colour string and an opacity into an ARGB integer (python: int(hex(opacity) + colour, 16)).
 * @param {string} colour - "RRGGBB"
 * @param {number} opacity - 0-255; out-of-range values become 255
 * @returns {number} unsigned 0xAARRGGBB
 */
function colourToHex(colour, opacity) {
  if (opacity < 0 || opacity > 255) opacity = 255;
  return (((opacity & 0xff) << 24) | (parseInt(colour, 16) & 0xffffff)) >>> 0;
}

/**
 * Draws a filled rectangle given in layout pixels (see LS). Edges are rounded rather than sizes, so neighbouring rectangles never leave gaps when scaled.
 * @param {number} left
 * @param {number} top
 * @param {number} width
 * @param {number} height
 * @param {number} color - ARGB
 */
function fillWin(left, top, width, height, color) {
  var scale_x = LAYOUT_SCALE.x, scale_y = LAYOUT_SCALE.y;
  var canvas_left = Math.round(left * scale_x);
  var canvas_top = Math.round(top * scale_y);
  var canvas_width = Math.round((left + width) * scale_x) - canvas_left;
  var canvas_height = Math.round((top + height) * scale_y) - canvas_top;
  if (width > 0 && canvas_width < 1) canvas_width = 1;
  if (height > 0 && canvas_height < 1) canvas_height = 1;
  if (canvas_width <= 0 || canvas_height <= 0) return;
  sbpe.canvasFillRect(canvas_left, canvas_top, canvas_width, canvas_height, color);
}

/**
 * XDL_DrawRect equivalent: a 1px outline from (x, y) to (x + w, y + h) inclusive, in layout pixels.
 * @param {number} left
 * @param {number} top
 * @param {number} width
 * @param {number} height
 * @param {number} color - ARGB
 */
function strokeWin(left, top, width, height, color) {
  fillWin(left, top, width + 1, 1, color);              // top edge
  fillWin(left, top + height, width + 1, 1, color);     // bottom edge
  fillWin(left, top, 1, height + 1, color);             // left edge
  fillWin(left + width, top, 1, height + 1, color);     // right edge
}

// ---------------------------------------------------------------------------
// layout objects (GraphicWindow / PanelGroup / labels), ported as they were
// ---------------------------------------------------------------------------

/**
 * Base of everything that is laid out and drawn: a rectangle with an optional background and border (the python Graphic).
 */
class Graphic {
  /**
   * @param {Object} host - the Plugin, used to get cached text
   */
  constructor(host) {
    this.host = host;
    this.left = -1; this.top = -1; this.width = 0; this.height = 0;
    this.fill_rect_colour = '2B2B2B';
    this.fill_rect_opacity = 255;
    this.draw_rect_colour = 'A0A0A0';
    this.draw_rect_opacity = 255;
    this.draw_top_border = false;
    this.draw_bottom_border = false;
    this.draw_right_border = false;
    this.draw_left_border = false;
    this.display_fill_rect = true;
  }
  /**
   * Toggles all four borders (the python does the same; called once per box, so it turns the border on).
   */
  drawBorder() {   // toggles, like the python
    this.draw_top_border = !this.draw_top_border;
    this.draw_bottom_border = !this.draw_bottom_border;
    this.draw_right_border = !this.draw_right_border;
    this.draw_left_border = !this.draw_left_border;
  }
  /**
   * @param {number} opacity - background opacity, 0-255
   */
  setFillRectOpacity(opacity) { this.fill_rect_opacity = opacity; }
  /**
   * @param {number} opacity - border opacity, 0-255
   */
  setDrawRectOpacity(opacity) { this.draw_rect_opacity = opacity; }
  /**
   * @param {string} colour - background colour "RRGGBB"
   */
  setFillRectColour(colour) { this.fill_rect_colour = colour; }
  /**
   * @param {string} colour - border colour "RRGGBB"
   */
  setDrawRectColour(colour) { this.draw_rect_colour = colour; }
  /**
   * @param {boolean} is_shown - whether the background is drawn
   */
  displayFillRect(is_shown) { this.display_fill_rect = is_shown; }
  /**
   * Draws the background and the border. The python passes zeros for sides without a border, which draws nothing, so nothing is drawn unless all four borders are on.
   */
  draw() {   // background and border
    if (this.display_fill_rect) {
      fillWin(this.left, this.top, this.width, this.height, colourToHex(this.fill_rect_colour, this.fill_rect_opacity));
    }
    // the python passes zeros for sides without a border, which draws nothing
    if (this.draw_top_border && this.draw_bottom_border && this.draw_right_border && this.draw_left_border) {
      strokeWin(this.left, this.top, this.width, this.height, colourToHex(this.draw_rect_colour, this.draw_rect_opacity));
    }
  }
}

/**
 * A child element of a box: a label or a divider.
 */
class GraphicPanel extends Graphic {
  /**
   * @param {Object} host - the Plugin
   * @param {GraphicWindow} window - the box this panel belongs to
   */
  constructor(host, window) { super(host); this.window = window; }
  /**
   * Panels draw nothing by default; subclasses override this.
   */
  draw() {}
}

/**
 * A thin horizontal line between two items (4px tall).
 */
class GraphicPanelDivider extends GraphicPanel {
  /**
   * @param {Object} host - the Plugin
   * @param {GraphicWindow} window - the box it is drawn in
   * @param {(GraphicWindow|PanelGroup)} parent - what positions it
   */
  constructor(host, window, parent) { super(host, window); this.height = DIVIDER_HEIGHT; this.parent = parent; }
  /**
   * Draws the line across the box, inset 11px on both sides.
   */
  draw() {
    var parent_window = this.window;
    fillWin(parent_window.left + DIVIDER_INSET, parent_window.top + this.top,
            parent_window.width - 2 * DIVIDER_INSET, 1, DIVIDER_COLOUR);
  }
}

/**
 * One line of text. Its width is the text width plus 32px padding on each side; it is 22px tall.
 */
class GraphicPanelLabel extends GraphicPanel {
  /**
   * @param {Object} host - the Plugin (provides cached text)
   * @param {GraphicWindow} window - the box it is drawn in
   * @param {(GraphicWindow|PanelGroup)} parent - what positions it
   * @param {string} text
   * @param {number} position - indent level, 0 = item name, 1 = modifier; each level adds 10px
   * @param {number} colour - text colour as an RGB integer
   * @param {number} opacity - text opacity
   */
  constructor(host, window, parent, text, position, colour, opacity) {
    super(host, window);
    this.height = LABEL_HEIGHT;
    this.position = position;
    this.parent = parent;
    this.text_spacing_x = INDENT_PER_POSITION * position;
    this.label_spacing_x = LABEL_PADDING_X;
    this.text_spacing_y = LABEL_TEXT_OFFSET_Y;
    this.colour = colour;
    this.opacity = opacity;
    this.cached_text = null;
    this.has_text = false;
    if (text !== null && text !== undefined) this.setText(text);
  }
  /**
   * Gets the cached text for this label and updates its width. Empty text has the padding width only and draws nothing.
   * @param {string} label_text
   */
  setText(label_text) {
    if (label_text) {
      this.cached_text = this.host.labelText(label_text, this.colour, this.opacity);   // {width, draw(left, top)}
      this.width = this.cached_text.width + 2 * this.label_spacing_x;
      this.has_text = true;
    } else {
      this.width = 2 * this.label_spacing_x;
      this.has_text = false;
    }
  }
  /**
   * Draws the text inside the label, offset by the box position and the label's indent.
   */
  draw() {
    if (this.has_text) {
      this.cached_text.draw(this.window.left + this.left + this.text_spacing_x,
                            this.window.top + this.top + this.text_spacing_y);
    }
  }
}

/**
 * An item with its modifiers: a label plus child labels/dividers, optionally with a coloured background. Always lives inside a GraphicWindow.
 */
class PanelGroup extends Graphic {
  /**
   * @param {Object} host - the Plugin
   * @param {GraphicWindow} window - the box it belongs to
   * @param {string} tag - name, for debugging
   */
  constructor(host, window, tag) {
    super(host);
    this.tag = tag;
    this.window = window;
    this.set_fill_rect = '';
    this.set_draw_rect = '';
    this.set_fill_rect_opacity = 0;
    this.set_draw_rect_opacity = 0;
    this.panel_horizontal_spacing = PANEL_HORIZONTAL_SPACING;
    this.panel_vertical_spacing = PANEL_VERTICAL_SPACING;
    this.text_position = 0;
    this.base_window_y = 0;
    this.base_window_x = 0;
    this.levels = 0;
    this.panels = [];
    this.parent = null;
  }
  /**
   * @param {PanelGroup} child_group - nested group
   */
  addPanelGroup(child_group) { this.panels.push(child_group); child_group.parent = this; }
  /**
   * Adds a text line to the group.
   * @param {string} text
   * @param {number} position - indent level, see GraphicPanelLabel
   * @param {string} colour - "RRGGBB"
   * @param {number} opacity
   */
  addLabel(text, position, colour, opacity) {
    this.panels.push(new GraphicPanelLabel(this.host, this.window, this, text, position, parseInt(colour, 16), opacity));
  }
  /**
   * Adds a divider line to the group.
   */
  addPanelDivider() { this.panels.push(new GraphicPanelDivider(this.host, this.window, this)); }
  /**
   * Overrides the group's background colour (otherwise it uses the box's).
   * @param {string} colour_hex - "RRGGBB"
   * @param {number} opacity - 0-255
   */
  changeFillRectColour(colour_hex, opacity) { this.set_fill_rect = colour_hex; this.set_fill_rect_opacity = opacity; }
  /**
   * Overrides the group's border colour (otherwise it uses the box's).
   * @param {string} colour_hex - "RRGGBB"
   * @param {number} opacity - 0-255
   */
  changeDrawRectColour(colour_hex, opacity) { this.set_draw_rect = colour_hex; this.set_draw_rect_opacity = opacity; }
  /**
   * Sums up the group's size: width of the box, height of all its panels.
   * @param {Array} panels - the panels to measure
   */
  defineWindow(panels) {
    for (var panel_index = 0; panel_index < panels.length; panel_index++) {
      var panel = panels[panel_index];
      if (panel instanceof PanelGroup) this.defineWindow(panel.panels);
      else { this.width = this.window.width; this.height += panel.height; }
    }
  }
  /**
   * Resolves which background/border colours the group uses: its own if set, else the box's.
   */
  setDisplayColour() {
    var parent_window = this.window;
    if (this.set_fill_rect === '' && parent_window) {
      if (parent_window.fill_rect_colour !== '') {
        this.setFillRectColour(parent_window.fill_rect_colour);
        this.setFillRectOpacity(parent_window.fill_rect_opacity);
      }
    } else if (this.set_fill_rect !== '') {
      this.setFillRectColour(this.set_fill_rect);
      this.setFillRectOpacity(this.set_fill_rect_opacity);
    }
    if (this.set_draw_rect === '' && parent_window) {
      if (parent_window.draw_rect_colour !== '') {
        this.setDrawRectColour(parent_window.draw_rect_colour);
        this.setDrawRectOpacity(parent_window.draw_rect_opacity);
      }
    } else if (this.set_draw_rect !== '') {
      this.setDrawRectColour(this.set_draw_rect);
      this.setDrawRectOpacity(this.set_draw_rect_opacity);
    }
  }
  /**
   * Positions the group's panels top to bottom inside the box.
   * @param {Array} panels
   * @param {number} window_left - left of the box
   * @param {number} top_in_window - vertical position inside the box
   */
  renderNestedPanels(panels, window_left, top_in_window) {
    for (var panel_index = 0; panel_index < panels.length; panel_index++) {
      var panel = panels[panel_index];
      if (panel instanceof PanelGroup) {
        this.text_position += panel.reset(window_left, this.text_position + this.panel_vertical_spacing,
                                          this.width, 1, this.base_window_y);
      } else {
        panel.left = this.panel_horizontal_spacing + (this.levels * INDENT_PER_LEVEL);
        panel.top = this.text_position;
        this.text_position += panel.height;
      }
    }
  }
  /**
   * Positions the group for this frame. Sizes are recomputed from scratch, because the layout objects are rebuilt every frame in the python and the state must not accumulate.
   * @param {number} window_left - left of the box
   * @param {number} top_in_window - vertical position inside the box
   * @param {number} levels - nesting depth (indents the labels)
   * @param {number} base_window_y - top of the box
   * @param {number} base_window_x - left of the box
   * @returns {number} height the group takes in the box
   */
  reset(window_left, top_in_window, levels, base_window_y, base_window_x) {
    this.setDisplayColour();
    this.base_window_y = base_window_y;
    this.levels = levels;
    this.top = base_window_y + top_in_window;
    this.left = base_window_x;
    this.text_position = top_in_window;
    this.height = 0;
    this.defineWindow(this.panels);
    this.width = this.width - 1;
    this.height = this.height - 2;
    this.renderNestedPanels(this.panels, window_left, top_in_window);
    return this.height;
  }
  /**
   * Draws the group's background and all its panels.
   */
  draw() {
    super.draw();
    for (var panel_index = 0; panel_index < this.panels.length; panel_index++) this.panels[panel_index].draw();
  }
}

/**
 * One box of loot above a chest: a background, a border and a list of labels, dividers and PanelGroups.
 */
class GraphicWindow extends Graphic {
  /**
   * @param {Object} host - the Plugin
   */
  constructor(host) {
    super(host);
    this.panel_horizontal_spacing = PANEL_HORIZONTAL_SPACING;
    this.panel_vertical_spacing = PANEL_VERTICAL_SPACING;
    this.text_position = 0;
    this.base_window_y = 0;
    this.base_window_x = 0;
    this.panels = [];
    this.panel_is_first_item = true;
  }
  /**
   * @param {PanelGroup} g - an item with its modifiers
   */
  addPanelGroup(panel_group) { this.panels.push(panel_group); }
  /**
   * Adds a text line directly to the box.
   * @param {string} text
   * @param {number} position - indent level, see GraphicPanelLabel
   * @param {string} colour - "RRGGBB"
   * @param {number} opacity
   */
  addLabel(text, position, colour, opacity) {
    this.panels.push(new GraphicPanelLabel(this.host, this, this, text, position, parseInt(colour, 16), opacity));
  }
  /**
   * Adds a divider line directly to the box.
   */
  addPanelDivider() { this.panels.push(new GraphicPanelDivider(this.host, this, this)); }
  /**
   * Computes the box size from its content: widest label (+6px) by the sum of all panel heights.
   * @param {Array} panels
   * @param {boolean} is_nested_call - true on recursive calls, so the size isn't reset
   */
  defineWindow(panels, is_nested_call) {
    if (!is_nested_call) { this.width = 0; this.height = 0; }
    for (var panel_index = 0; panel_index < panels.length; panel_index++) {
      var panel = panels[panel_index];
      if (panel instanceof PanelGroup) this.defineWindow(panel.panels, true);
      else {
        this.width = Math.max(this.width, panel.width + 2 * this.panel_horizontal_spacing);
        this.height += panel.height;
      }
    }
  }
  /**
   * Positions the box's panels and PanelGroups top to bottom.
   * @param {Array} panels
   */
  renderNestedPanels(panels) {
    for (var panel_index = 0; panel_index < panels.length; panel_index++) {
      var panel = panels[panel_index];
      if (panel instanceof PanelGroup) {
        if (this.panel_is_first_item) {
          this.text_position += panel.reset(this.left, this.text_position + 1, 1, this.base_window_y, this.base_window_x);
          this.panel_is_first_item = false;
        } else {
          this.text_position += panel.reset(this.left, this.text_position, 1, this.base_window_y, this.base_window_x);
        }
        this.renderNestedPanels(panel.panels);
      } else if (!(panel.parent instanceof PanelGroup)) {
        panel.left = this.panel_horizontal_spacing;
        panel.top = this.text_position;
        this.text_position += panel.height;
      }
      this.panel_is_first_item = false;
    }
  }
  /**
   * Moves the box and lays out its content for this frame.
   * @param {number} left
   * @param {number} top
   */
  reset(left, top) {
    this.text_position = 0;
    this.panel_is_first_item = true;
    this.left = left;
    this.top = top;
    this.base_window_y = top;
    this.base_window_x = left;
    this.renderNestedPanels(this.panels);
  }
  /**
   * Draws the box background, border and all content.
   */
  draw() {
    super.draw();
    for (var panel_index = 0; panel_index < this.panels.length; panel_index++) this.panels[panel_index].draw();
  }
}

// ---------------------------------------------------------------------------
// the plugin
// ---------------------------------------------------------------------------

// options that only change positioning/drawing, not the computed chest data
var VIEW_ONLY = {
  scd_display_box: 1, scd_scale_with_zoom: 1, scd_min_scale: 1, scd_max_items_per_box: 1, scd_display_x_spacing: 1, scd_display_y_spacing: 1,
  scd_display_background_colour: 1, scd_display_background_colour_opacity: 1,
  scd_display_border_colour: 1, scd_display_border_colour_opacity: 1,
  scd_display_container_background: 1, scd_display_panel_group_background: 1,
  scd_disable_on_walk_over: 1, scd_enable_on_walk_over: 1, scd_equal_chest_display: 1
};

/**
 * The sb_chest_display plugin: reads chests in afterUpdate and draws their boxes in onPresent.
 */
class Plugin extends sbpe.PluginBase {
  /**
   * Registers all scd_* config options (same names and defaults as the python plugin, plus scd_scale_with_zoom and scd_min_scale) and creates the plugin state.
   */
  onInit() {
    this.config.options('int', {
      scd_text_display_size: 15,
      scd_max_items_per_box: 20,
      scd_display_x_spacing: 25,
      scd_display_y_spacing: 15,

      scd_display_background_colour_opacity: 255,
      scd_display_border_colour_opacity: 255,

      scd_common_fill_background_colour_opacity: 255,
      scd_modified_fill_background_colour_opacity: 255,
      scd_custom_fill_background_colour_opacity: 255,
      scd_experimental_fill_background_colour_opacity: 255,
      scd_prototype_fill_background_colour_opacity: 255,
      scd_perf_item_fill_background_colour_opacity: 255
    });

    this.config.options('float', {
      scd_min_scale: 0.75,

      scd_text_common_label_colour_opacity: 1.0,
      scd_text_modified_label_colour_opacity: 1.0,
      scd_text_custom_label_colour_opacity: 1.0,
      scd_text_experimental_label_colour_opacity: 1.0,
      scd_text_prototype_label_colour_opacity: 1.0,
      scd_text_perf_item_label_colour_opacity: 1.0,

      scd_text_modified_modifier_colour_opacity: 1.0,
      scd_text_custom_modifier_colour_opacity: 1.0,
      scd_text_experimental_modifier_colour_opacity: 1.0,
      scd_text_prototype_modifier_colour_opacity: 1.0,
      scd_text_perf_item_modifier_colour_opacity: 1.0
    });

    this.config.options('str', {
      scd_common_fill_background_colour: 'ffffff',
      scd_modified_fill_background_colour: '79f071',
      scd_custom_fill_background_colour: '3d70f0',
      scd_experimental_fill_background_colour: 'd04ef0',
      scd_prototype_fill_background_colour: 'f0b03d',
      scd_perf_item_fill_background_colour: 'd22b2b',

      scd_text_common_label_colour: 'FFFFFF',
      scd_text_modified_label_colour: '1DB113',
      scd_text_custom_label_colour: '3D70F0',
      scd_text_experimental_label_colour: 'D04EF0',
      scd_text_prototype_label_colour: 'F0B03D',
      scd_text_perf_item_label_colour: 'D22B2B',

      scd_text_modified_modifier_colour: '79F071',
      scd_text_custom_modifier_colour: '638CF3',
      scd_text_experimental_modifier_colour: 'DE83F4',
      scd_text_prototype_modifier_colour: 'F6D291',
      scd_text_perf_item_modifier_colour: 'DF6A6A',

      scd_display_background_colour: '2B2B2B',
      scd_display_border_colour: 'A0A0A0'
    });

    this.config.options('bool', {
      scd_display_box: true,
      scd_scale_with_zoom: true,
      scd_display_container_background: true,
      scd_display_panel_group_background: false,
      scd_ec_uc_compress: false,
      scd_item_compress: false,
      scd_remove_filter: false,
      scd_display_filter: false,
      scd_disable_on_walk_over: false,
      scd_enable_on_walk_over: false,
      scd_equal_chest_display: false
    });

    this.should_draw = false;
    this.chest_objects = [];               // chest objects in the current subworld
    this.chest_data_by_id = new Map();     // chest objId -> {hash, display, length}
    this.settings_signature = '';
    this.text_cache = new Map();           // see labelText
    this.frame_counter = 0;
  }

  /**
   * Gets (creating it if needed) the cached text object for a label.
   * Text textures are cached because JS can't free them automatically like python and the layout is rebuilt every frame. The font is rendered at 13px * the layout scale (LS) and blitted 1:1, so scaling never squashes (blurs) the text; widths are reported in layout pixels as if rendered at 13px.
   * @param {string} text
   * @param {number} rgb - colour as an RGB integer
   * @param {number} alpha - 0-1
   * @returns {{text_object: Object, last_used_frame: number, width: number, draw: function(number, number)}} width is in layout px; draw(left, top) takes layout px
   */
  labelText(text, rgb, alpha) {
    var font_size_px = Math.max(MIN_FONT_SIZE, Math.round(FONT_BASE_SIZE * LAYOUT_SCALE.x));
    var cache_key = text + '\u0000' + rgb + '\u0000' + alpha + '\u0000' + font_size_px;
    var cached_label = this.text_cache.get(cache_key);
    if (!cached_label) {
      var text_object = new util.PlainText({ size: font_size_px, outlineSize: 0 });   // size should be 12 but the real font size is set to 10
      text_object.color = rgb;
      text_object.alpha = alpha;
      text_object.text = text;
      text_object.updateTexture();     // the width is needed for the layout
      text_object._dirty = false;
      cached_label = {
        text_object: text_object,
        last_used_frame: 0,
        width: Math.round(text_object.w * FONT_BASE_SIZE / font_size_px),
        /**
         * Draws the text 1:1 in canvas pixels.
         * @param {number} left - in layout pixels
         * @param {number} top - in layout pixels
         */
        draw: function (left, top) {
          var saved_scale_x = refs.scaleX, saved_scale_y = refs.scaleY;
          refs.scaleX = refs.scaleY = 1;      // PlainText.draw scales by these; we pass canvas pixels
          try { text_object.draw(Math.round(left * LAYOUT_SCALE.x), Math.round(top * LAYOUT_SCALE.y)); }
          finally { refs.scaleX = saved_scale_x; refs.scaleY = saved_scale_y; }
        }
      };
      this.text_cache.set(cache_key, cached_label);
    }
    cached_label.last_used_frame = this.frame_counter;
    return cached_label;
  }

  /**
   * Destroys cached text textures that haven't been used for 180 frames.
   */
  pruneText() {
    var plugin = this;
    Array.from(this.text_cache.keys()).forEach(function (cache_key) {
      var cached_label = plugin.text_cache.get(cache_key);
      if (plugin.frame_counter - cached_label.last_used_frame > TEXT_CACHE_MAX_AGE_FRAMES) {
        cached_label.text_object.destroy();
        plugin.text_cache.delete(cache_key);
      }
    });
  }

  /**
   * Signature of every option that affects the computed chest data; when it changes the cache is cleared so setting changes apply live.
   * @returns {string}
   */
  configSig() {
    var config = this.config, signature_parts = [];
    Object.keys(config._schema).forEach(function (option_name) {
      if (!VIEW_ONLY[option_name]) signature_parts.push(config[option_name]);
    });
    return signature_parts.join('|');
  }

  /**
   * Applies the remove/display filters, EC/UC and duplicate compression and perf-item detection to a chest's loot (the per-chest part of the python afterUpdate).
   * @param {{type: number, boosts: {stat: number, val: number}[]}[]} chest_items - the chest's loot
   * @param {number} contents_hash - fingerprint of chest_items, stored for change detection
   * @returns {{hash: number, display: Object[], length: number}} display entries and the number of text lines they take
   */
  computeChest(chest_items, contents_hash) {
    var config = this.config;
    var display_entries = [], chest_length = 0, total_ec = 0, total_uc = 0;
    var wildcard_filter_list = [];

    if (config.scd_remove_filter) {
      remove_filter_list.forEach(function (filter_entry) {
        if (!('modifiers' in filter_entry)) wildcard_filter_list.push(filter_entry.name);
      });
    } else if (config.scd_display_filter) {
      display_filter_list.forEach(function (filter_entry) {
        if (!('modifiers' in filter_entry)) wildcard_filter_list.push(filter_entry.name);
      });
    }
    /**
     * Whether the list has an entry with this name and exactly these modifiers (any order).
     * @param {{name: string, modifiers: string[]}[]} filter_list
     * @param {string} item_name
     * @param {string[]} boost_names
     * @returns {boolean}
     */
    function listed(filter_list, item_name, boost_names) {
      return filter_list.some(function (filter_entry) {
        return item_name === filter_entry.name && sameBag(filter_entry.modifiers || [], boost_names);
      });
    }

    for (var item_index = 0; item_index < chest_items.length; item_index++) {
      var chest_item = chest_items[item_index];
      var item_data = itemInfo(chest_item.type);
      var item_name = item_data.name;
      var item_boosts = chest_item.boosts;
      var item_boosts_names = item_boosts.map(function (boost) {
        return filterBoost(boost.stat, { class: item_data.class, slot: item_data.slot }).name;
      });

      var perf_item_match = false, perf_item_variant_name = '';
      for (var perf_index = 0; perf_index < perf_tracking.length; perf_index++) {
        var perf_entry = perf_tracking[perf_index];
        if (item_name === perf_entry.name && sameBag(perf_entry.modifiers, item_boosts_names) && perf_entry.tracking) {
          perf_item_match = true;
          perf_item_variant_name = perf_entry.variant;
        }
      }

      var currency = currencyOf(item_name);

      if (config.scd_remove_filter) {
        if (config.scd_ec_uc_compress && currency) {
          if (wildcard_filter_list.indexOf(currency.kind) !== -1) continue;
          if (currency.kind === 'EC') total_ec += currency.amount; else total_uc += currency.amount;
          continue;
        }
        if (wildcard_filter_list.indexOf(item_name) !== -1) continue;
        if (item_boosts_names.length > 0 && listed(remove_filter_list, item_name, item_boosts_names)) continue;
      } else if (config.scd_display_filter) {
        if (config.scd_ec_uc_compress && currency) {
          if (wildcard_filter_list.indexOf(currency.kind) !== -1) {
            if (currency.kind === 'EC') total_ec += currency.amount; else total_uc += currency.amount;
          }
          continue;
        }
        if (wildcard_filter_list.indexOf(item_name) === -1) {
          if (item_boosts_names.length > 0 && listed(display_filter_list, item_name, item_boosts_names)) {
            // matched modifiers: show it
          } else continue;
        }
      } else if (config.scd_ec_uc_compress && currency) {
        if (currency.kind === 'EC') total_ec += currency.amount; else total_uc += currency.amount;
        continue;
      }

      var logging_name;
      if (perf_item_match) logging_name = perf_item_variant_name + ' ' + item_name;
      else logging_name = item_boosts.length > 0 ? (ITEM_MODS[item_boosts.length] || '') + ' ' + item_name : item_name;

      var item_display_entry = addItemToLoggingDisplay(config, item_data, logging_name, item_boosts, perf_item_match);

      // given we store the readable text, duplicates are compared after formatting
      if (config.scd_item_compress) {
        var item_exists = false;
        var item_boost_texts = item_display_entry.boosts.map(function (boost_entry) { return boost_entry.text; });
        for (var existing_index = 0; existing_index < display_entries.length; existing_index++) {
          var existing_entry = display_entries[existing_index];
          var existing_boost_texts = existing_entry.boosts.map(function (boost_entry) { return boost_entry.text; });
          if (item_display_entry.item.text === existing_entry.item.text &&
              sameBag(item_boost_texts, existing_boost_texts)) {
            existing_entry.item.amount += 1;
            item_exists = true;
            break;
          }
        }
        if (!item_exists) { chest_length += item_boosts.length + 1; display_entries.push(item_display_entry); }
      } else {
        chest_length += item_boosts.length + 1;
        display_entries.push(item_display_entry);
      }
    }

    if (total_ec > 0) display_entries.push(addPlainToLoggingDisplay(config, total_ec + ' EC'));
    if (total_uc > 0) display_entries.push(addPlainToLoggingDisplay(config, total_uc + ' UC'));
    return { hash: contents_hash, display: display_entries, length: chest_length };
  }

  /**
   * Per-frame update: collects the chests in the current subworld and refreshes the cached data of new or changed ones. Does nothing in IGNORED_ZONE.
   */
  afterUpdate() {
    this.should_draw = false;
    this.chest_objects = [];
    this.frame_counter++;

    var client_world = this.refs.ClientWorld, world_view = this.refs.WorldView;
    if (!client_world || !world_view || !client_world.mySubWorld) return;

    var zone = zoneName(client_world.props);
    if (IGNORED_ZONE.indexOf(zone) === -1) {
      // chest data is cached until the chest's contents or the settings change
      var settings_signature = this.configSig();
      if (settings_signature !== this.settings_signature) {
        this.settings_signature = settings_signature;
        this.chest_data_by_id.clear();
      }

      var seen_chest_ids = new Set();
      var world_objects = util.worldobjects(client_world.mySubWorld.asNativeSubWorld);
      for (var object_index = 0; object_index < world_objects.length; object_index++) {
        var world_object = world_objects[object_index];
        if (mem.className(world_object.address) !== 'Chest') continue;
        var chest_id = world_object.objId;
        seen_chest_ids.add(chest_id);
        this.chest_objects.push(world_object);
        var chest_items = readChestItems(mem.cast('Chest', world_object.address));
        var contents_hash = hashEntries(chest_items);
        var cached_chest_data = this.chest_data_by_id.get(chest_id);
        if (!cached_chest_data || cached_chest_data.hash !== contents_hash) {
          this.chest_data_by_id.set(chest_id, this.computeChest(chest_items, contents_hash));
        }
      }
      // chests that are gone (floor change, opened and removed, home)
      var plugin = this;
      Array.from(this.chest_data_by_id.keys()).forEach(function (chest_id) {
        if (!seen_chest_ids.has(chest_id)) plugin.chest_data_by_id.delete(chest_id);
      });
    } else {
      this.chest_data_by_id.clear();
    }

    this.should_draw = true;
    if (this.frame_counter % TEXT_CACHE_PRUNE_INTERVAL_FRAMES === 0) this.pruneText();
  }

  /**
   * Builds the boxes for one chest, splitting the lines over up to three side-by-side boxes.
   * @param {Object[]} display_entries - computeChest display entries
   * @param {number} chest_length - number of text lines in total
   * @returns {GraphicWindow[]} one to three boxes, sized but not yet positioned
   */
  buildDisplays(display_entries, chest_length) {
    var config = this.config;
    var plugin = this;

    /**
     * Creates an empty box with the configured background and border colours.
     * @returns {GraphicWindow}
     */
    function newWindow() {
      var loot_box = new GraphicWindow(plugin);
      loot_box.setFillRectColour(config.scd_display_background_colour);
      loot_box.setDrawRectColour(config.scd_display_border_colour);
      loot_box.setFillRectOpacity(config.scd_display_background_colour_opacity);
      loot_box.setDrawRectOpacity(config.scd_display_border_colour_opacity);
      return loot_box;
    }

    var loot_boxes = [newWindow()];
    var current_box_index = 0, panel_group_number = 0, lines_in_current_box = 0, total_boxes;

    if (chest_length <= config.scd_max_items_per_box) total_boxes = 1;
    else if (chest_length <= config.scd_max_items_per_box * 2) total_boxes = 2;
    else total_boxes = 3;

    var max_lines_per_box = config.scd_max_items_per_box;
    if (config.scd_equal_chest_display && total_boxes > 1) max_lines_per_box = Math.trunc(chest_length / total_boxes);

    for (var entry_index = 0; entry_index < display_entries.length; entry_index++) {
      var display_entry = display_entries[entry_index];
      var is_last_entry = entry_index === display_entries.length - 1;

      if (lines_in_current_box >= max_lines_per_box && current_box_index !== total_boxes - 1) {
        loot_boxes.push(newWindow());
        current_box_index++;
        lines_in_current_box = 0;
      }

      var label_text = display_entry.item.amount === 1
        ? display_entry.item.text
        : display_entry.item.amount + ' ' + display_entry.item.text;

      if (display_entry.boosts.length === 0) {
        lines_in_current_box++;
        loot_boxes[current_box_index].addLabel(label_text, 1, config.scd_text_common_label_colour,
                                               config.scd_text_common_label_colour_opacity);

        // a divider unless this is the last entry
        if (current_box_index === total_boxes - 1 && !is_last_entry) loot_boxes[current_box_index].addPanelDivider();
        else if (lines_in_current_box < max_lines_per_box && !is_last_entry) loot_boxes[current_box_index].addPanelDivider();
      } else {
        panel_group_number++;
        var panel_group = new PanelGroup(this, loot_boxes[current_box_index], 'pg' + panel_group_number);
        panel_group.displayFillRect(config.scd_display_panel_group_background);
        panel_group.changeFillRectColour(display_entry.item.fill_background, display_entry.item.fill_background_opacity);

        lines_in_current_box++;
        panel_group.addLabel(label_text, 0, display_entry.item.label_colour, display_entry.item.label_opacity);

        for (var boost_index = 0; boost_index < display_entry.boosts.length; boost_index++) {
          lines_in_current_box++;
          panel_group.addLabel(display_entry.boosts[boost_index].text, 1,
                               display_entry.boosts[boost_index].colour, display_entry.boosts[boost_index].opacity);
        }

        if (current_box_index === total_boxes - 1 && !is_last_entry) panel_group.addPanelDivider();
        else if (lines_in_current_box < max_lines_per_box && !is_last_entry) panel_group.addPanelDivider();

        loot_boxes[current_box_index].addPanelGroup(panel_group);
      }
    }

    loot_boxes.forEach(function (loot_box) {
      loot_box.drawBorder();
      loot_box.displayFillRect(config.scd_display_container_background);
      loot_box.defineWindow(loot_box.panels, false);
    });
    return loot_boxes;
  }

  /**
   * Per-frame draw: positions the boxes above each closed chest (keeping them on screen horizontally), applies the walk-over options and draws them. With scd_scale_with_zoom on, the boxes shrink and grow with the zoom like the HUD but never get smaller than scd_min_scale of their normal size; with it off they keep a fixed size on screen.
   */
  onPresent() {
    if (!this.should_draw || !this.config.scd_display_box) return;

    var client_world = this.refs.ClientWorld, world_view = this.refs.WorldView;
    if (!client_world || !world_view || !client_world.player || this.chest_objects.length === 0) return;

    var config = this.config;
    // boxes either scale with the zoom (layout in canvas px) or keep a fixed window size
    var scales_with_zoom = config.scd_scale_with_zoom;
    if (scales_with_zoom) {
      // shrink with the zoom like the HUD, but not below scd_min_scale of the normal size
      LAYOUT_SCALE.x = Math.max(1, config.scd_min_scale * this.refs.scaleX);
      LAYOUT_SCALE.y = Math.max(1, config.scd_min_scale * this.refs.scaleY);
    } else {
      LAYOUT_SCALE.x = this.refs.scaleX;
      LAYOUT_SCALE.y = this.refs.scaleY;
    }
    var scale_x = LAYOUT_SCALE.x, scale_y = LAYOUT_SCALE.y;
    var screen_width = scales_with_zoom ? this.refs.canvasW / scale_x : this.refs.windowW;
    var camera_offset = world_view.offset;
    var vertical_spacing = config.scd_display_y_spacing;
    var horizontal_spacing = config.scd_display_x_spacing;
    var half_horizontal_spacing = Math.trunc(horizontal_spacing / 2);

    var player_props = mem.cast('WorldObject', client_world.player).props;
    var player_position = toLayoutPosition(player_props, camera_offset, scale_x, scale_y);

    for (var chest_index = 0; chest_index < this.chest_objects.length; chest_index++) {
      var chest_object = this.chest_objects[chest_index];

      // remove the display once the chest is opened
      if (mem.cast('Chest', chest_object.address).pos !== -1) continue;

      // catch the race where the chest isn't in the cache yet
      var chest_data = this.chest_data_by_id.get(chest_object.objId);
      if (!chest_data) continue;

      // layout coords (also correct when the zoom level changes)
      var chest_position = toLayoutPosition(chest_object.props, camera_offset, scale_x, scale_y);
      var chest_centre_x = chest_position.x, chest_top_y = chest_position.y;

      var loot_boxes = this.buildDisplays(chest_data.display, chest_data.length);
      var touch_box_left, touch_box_right, touch_box_top, touch_box_bottom;
      var first_box_left, second_box_left, third_box_left;
      var first_box_width = loot_boxes[0].width;

      if (loot_boxes.length === 1) {
        // [ [1**] [] [] ]
        first_box_left = chest_centre_x - Math.trunc(first_box_width / 2);
        touch_box_top = chest_top_y - loot_boxes[0].height - vertical_spacing;
        touch_box_bottom = chest_top_y - vertical_spacing;
        touch_box_left = first_box_left;
        touch_box_right = first_box_left + first_box_width;
        loot_boxes[0].reset(first_box_left, touch_box_top);
      } else if (loot_boxes.length === 2) {
        // [ [1**] [2**] [] ]
        var second_box_width = loot_boxes[1].width;
        var tallest_box_height = Math.max(loot_boxes[0].height, loot_boxes[1].height);

        first_box_left = chest_centre_x - first_box_width - half_horizontal_spacing;
        second_box_left = chest_centre_x + half_horizontal_spacing;
        touch_box_top = chest_top_y - tallest_box_height - vertical_spacing;
        touch_box_bottom = chest_top_y - vertical_spacing;
        touch_box_left = first_box_left;
        touch_box_right = second_box_left + second_box_width;

        if (first_box_left < 0) {
          // too far left: put both boxes to the right of the first box's centre
          first_box_left = chest_centre_x - Math.trunc(first_box_width / 2);
          second_box_left = chest_centre_x + Math.trunc(first_box_width / 2) + horizontal_spacing;
          touch_box_left = first_box_left;
          touch_box_right = second_box_left + second_box_width;
        } else if (second_box_left + second_box_width > screen_width) {
          // too far right: put the second box to the left of the first
          first_box_left = chest_centre_x - Math.trunc(first_box_width / 2);
          second_box_left = chest_centre_x - Math.trunc(first_box_width / 2) - second_box_width - horizontal_spacing;
          touch_box_left = second_box_left;
          touch_box_right = first_box_left + first_box_width;
        }

        loot_boxes[0].reset(first_box_left, chest_top_y - loot_boxes[0].height - vertical_spacing);
        loot_boxes[1].reset(second_box_left, chest_top_y - loot_boxes[1].height - vertical_spacing);
      } else {
        // [ [1**] [2**] [3**] ]
        var middle_box_width = loot_boxes[1].width, third_box_width = loot_boxes[2].width;
        var tallest_of_three = Math.max(loot_boxes[0].height, loot_boxes[1].height, loot_boxes[2].height);

        first_box_left = chest_centre_x - Math.trunc(first_box_width / 2);
        second_box_left = chest_centre_x - Math.trunc(first_box_width / 2) - middle_box_width - horizontal_spacing;
        third_box_left = chest_centre_x + Math.trunc(first_box_width / 2) + horizontal_spacing;

        touch_box_top = chest_top_y - tallest_of_three - vertical_spacing;
        touch_box_bottom = chest_top_y - vertical_spacing;
        touch_box_left = second_box_left;
        touch_box_right = third_box_left + third_box_width;

        if (second_box_left < 0) {
          // too far left
          first_box_left = chest_centre_x - Math.trunc(first_box_width / 2);
          second_box_left = chest_centre_x + Math.trunc(first_box_width / 2) + horizontal_spacing;
          third_box_left = chest_centre_x + Math.trunc(first_box_width / 2) + middle_box_width + horizontal_spacing * 2;

          // check again if the display needs to be corrected with scale
          if (first_box_left < 0) {
            first_box_left = chest_centre_x - Math.trunc(first_box_width / 2);
            var overflow_to_the_left = first_box_left * -1;
            first_box_left += Math.trunc(overflow_to_the_left * scale_x);
            second_box_left += Math.trunc(overflow_to_the_left * scale_x);
            third_box_left += Math.trunc(overflow_to_the_left * scale_x);
          }

          touch_box_left = first_box_left;
          touch_box_right = third_box_left + third_box_width;
        } else if (third_box_left + third_box_width > screen_width) {
          // too far right
          first_box_left = chest_centre_x - Math.trunc(first_box_width / 2);
          second_box_left = chest_centre_x - Math.trunc(first_box_width / 2) - middle_box_width - horizontal_spacing;
          third_box_left = chest_centre_x - Math.trunc(first_box_width / 2) - middle_box_width - third_box_width - horizontal_spacing * 2;

          touch_box_left = third_box_left;
          touch_box_right = first_box_left + first_box_width;
        }

        loot_boxes[0].reset(first_box_left, chest_top_y - loot_boxes[0].height - vertical_spacing);
        loot_boxes[1].reset(second_box_left, chest_top_y - loot_boxes[1].height - vertical_spacing);
        loot_boxes[2].reset(third_box_left, chest_top_y - loot_boxes[2].height - vertical_spacing);
      }

      var player_is_inside_touch_box =
        player_position.y >= touch_box_top && player_position.y <= touch_box_bottom &&
        player_position.x >= touch_box_left && player_position.x <= touch_box_right;
      var is_visible;
      if (config.scd_disable_on_walk_over) is_visible = !player_is_inside_touch_box;
      else if (config.scd_enable_on_walk_over) is_visible = player_is_inside_touch_box;
      else is_visible = true;

      if (is_visible) {
        for (var box_index = 0; box_index < loot_boxes.length; box_index++) {
          if (loot_boxes[box_index].panels.length > 0) loot_boxes[box_index].draw();
        }
      }
    }
  }

  /**
   * Frees all cached text textures and chest data.
   */
  onUnload() {
    this.text_cache.forEach(function (cached_label) { cached_label.text_object.destroy(); });
    this.text_cache.clear();
    this.chest_data_by_id.clear();
  }
}

sbpe.register('sb_chest_display', Plugin);
});