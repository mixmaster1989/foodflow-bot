from handlers.marathon import curator_menu

from . import (
    admin,
    common,
    correction,
    curator,
    errors,
    fridge,
    global_input,
    herbalife,
    # Marathon handlers
    # Note: We import the sub-package or modules
    i_ate,
    menu,
    onboarding,
    receipt,
    recipes,
    saved_dishes,
    shopping,
    shopping_list,
    stats,
    support,
    user_settings,
    weight,
)

__all__ = [
    "common",
    "correction",
    "curator",
    "fridge",
    "i_ate",
    "menu",
    "onboarding",
    "receipt",
    "recipes",
    "shopping",
    "shopping_list",
    "stats",
    "user_settings",
    "weight",
    "admin",
    "support",
    "errors",
    "errors",
    "global_input",
    "saved_dishes",
    "herbalife",
    "curator_menu"
]

