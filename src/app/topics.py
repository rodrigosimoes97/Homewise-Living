from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Topic:
    slug: str
    name: str
    angle: str
    tag: str


TOPICS: list[Topic] = [
    # Home Organization
    Topic("declutter-guide", "Declutter Guide", "room-by-room decluttering strategies for US homes", "home-organization"),
    Topic("closet-organization", "Closet Organization", "maximizing closet space with smart storage solutions", "home-organization"),
    Topic("garage-organization", "Garage Organization", "turning cluttered garages into functional spaces", "home-organization"),
    Topic("pantry-organization", "Pantry Organization", "practical pantry systems for busy families", "home-organization"),
    # Kitchen & Cooking
    Topic("kitchen-essentials", "Kitchen Essentials", "must-have tools for everyday cooking", "kitchen"),
    Topic("meal-prep-tools", "Meal Prep Tools", "best kitchen gadgets for efficient meal preparation", "kitchen"),
    Topic("kitchen-storage", "Kitchen Storage", "smart storage ideas for small and large kitchens", "kitchen"),
    Topic("kitchen-upgrades", "Kitchen Upgrades", "affordable kitchen improvements that make a difference", "kitchen"),
    # Home Decor & Improvement
    Topic("living-room-decor", "Living Room Decor", "modern and cozy living room styling ideas", "decor"),
    Topic("bedroom-makeover", "Bedroom Makeover", "creating a relaxing bedroom retreat on any budget", "decor"),
    Topic("bathroom-refresh", "Bathroom Refresh", "simple bathroom upgrades for a spa-like feel", "decor"),
    Topic("wall-decor-ideas", "Wall Decor Ideas", "creative wall art and gallery wall inspiration", "decor"),
    # Garden & Outdoor Living
    Topic("beginner-gardening", "Beginner Gardening", "easy-to-grow plants and gardening basics for US climates", "garden"),
    Topic("patio-design", "Patio Design", "outdoor living spaces that extend your home", "garden"),
    Topic("container-gardening", "Container Gardening", "growing herbs, vegetables, and flowers in small spaces", "garden"),
    Topic("outdoor-entertaining", "Outdoor Entertaining", "backyard entertaining setups and essentials", "garden"),
    # Home Office & Smart Living
    Topic("home-office-setup", "Home Office Setup", "productive home office design and ergonomic tips", "home-office"),
    Topic("smart-home-basics", "Smart Home Basics", "getting started with smart home devices and automation", "home-office"),
    Topic("productivity-space", "Productivity Space", "designing spaces that boost focus and creativity", "home-office"),
    Topic("tech-for-home", "Tech for Home", "useful technology products for modern homes", "home-office"),
    # Pet-Friendly Home
    Topic("pet-friendly-furniture", "Pet-Friendly Furniture", "stylish furniture that stands up to pets", "pets"),
    Topic("pet-organization", "Pet Organization", "organizing pet supplies and creating pet zones", "pets"),
    Topic("pet-safe-plants", "Pet-Safe Plants", "indoor and outdoor plants that are safe for cats and dogs", "pets"),
    Topic("pet-home-tips", "Pet Home Tips", "making your home comfortable for pets and people", "pets"),
]

PRIORITY_TAGS = ["home-organization", "kitchen", "decor", "garden", "home-office", "pets"]


def pick_topic(
    recent_topics: list[str],
    recent_tags: list[str] | None = None,
    tag_counts: dict[str, int] | None = None,
    excluded_slugs: set[str] | None = None,
    topic_rotation: dict[str, int] | None = None,
) -> Topic:
    recent_tags = recent_tags or []
    tag_counts = tag_counts or {}
    excluded_slugs = excluded_slugs or set()
    topic_rotation = topic_rotation or {}

    by_tag: dict[str, list[Topic]] = {}
    for topic in TOPICS:
        by_tag.setdefault(topic.tag, []).append(topic)

    eligible_tags = [tag for tag in PRIORITY_TAGS if tag in by_tag]
    remaining = sorted(tag for tag in by_tag if tag not in PRIORITY_TAGS)
    ordered_tags = eligible_tags + remaining

    if len(recent_tags) >= 2 and recent_tags[-1] == recent_tags[-2]:
        ordered_tags = [tag for tag in ordered_tags if tag != recent_tags[-1]] or ordered_tags

    min_count = min((tag_counts.get(tag, 0) for tag in ordered_tags), default=0)
    underrepresented = [tag for tag in ordered_tags if tag_counts.get(tag, 0) == min_count]
    candidate_tags = underrepresented or ordered_tags
    chosen_tag = candidate_tags[0]

    recent_window = set(recent_topics[-12:])
    topics_for_tag = sorted(by_tag[chosen_tag], key=lambda item: item.slug)
    fresh_topics = [item for item in topics_for_tag if item.slug not in recent_window and item.slug not in excluded_slugs]
    available = fresh_topics or [item for item in topics_for_tag if item.slug not in excluded_slugs] or topics_for_tag

    rotation_index = int(topic_rotation.get(chosen_tag, 0)) % len(available)
    return available[rotation_index]
