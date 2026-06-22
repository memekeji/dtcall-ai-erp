from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def assert_not_contains(path, needle, message):
    content = read(path)
    if needle in content:
        raise AssertionError(f"{path}: {message}")


def assert_contains(path, needle, message):
    content = read(path)
    if needle not in content:
        raise AssertionError(f"{path}: {message}")


def main():
    views = "apps/home/views.py"
    dashboard_views = "apps/home/dashboard_views.py"
    business_template = "templates/home/business_dashboard.html"
    css = "static/css/tailwind-runtime-replacement.css"

    assert_not_contains(views, "random.randint", "dashboard charts must use real data, not random samples")
    assert_not_contains(views, "days=i *\n                        30", "dashboard month ranges must use calendar months")
    assert_not_contains(views, "create_time__lte=month_end", "month range end must be exclusive")
    assert_contains(views, "json.dumps(months", "dashboard chart labels must be JSON encoded")
    assert_contains(views, "json.dumps([item['name'] for item in pie_data]", "customer source labels must be JSON encoded")
    assert_not_contains(dashboard_views, "create_time__lte=month_end", "month range end must be exclusive")
    assert_not_contains(business_template, "forloop.second", "Django templates do not expose forloop.second")
    assert_not_contains(business_template, "forloop.third", "Django templates do not expose forloop.third")

    required_css = [
        ".mx-6",
        ".border-b-2",
        ".border-t",
        ".border-orange-400",
        ".bg-grid",
        ".bg-success",
        ".text-teal-600",
        "[class~=\"focus:ring-primary/50\"]",
        "[class~=\"hover:bg-gray-800/30\"]",
    ]
    for selector in required_css:
        assert_contains(css, selector, f"missing local Tailwind replacement selector {selector}")


if __name__ == "__main__":
    main()
