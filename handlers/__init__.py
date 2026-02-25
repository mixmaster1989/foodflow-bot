from . import (
    common,
    correction,
    curator,
    fridge,
    i_ate,
    menu,
    onboarding,
    receipt,
    recipes,
    shopping,
    shopping_list,
    stats,
    user_settings,
    weight,
    admin,
    support,
    errors,
    errors,
    global_input,
    saved_dishes,
    herbalife,
    # Marathon handlers
    # Note: We import the sub-package or modules
)
from handlers.marathon import curator_menu

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

