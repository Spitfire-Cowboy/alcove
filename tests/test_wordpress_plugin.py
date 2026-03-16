import subprocess
import sys
import zipfile


def test_wordpress_plugin_command_exports_zip(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "alcove", "wordpress-plugin", "--output", str(tmp_path)],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    zip_path = tmp_path / "alcove-search-wordpress.zip"
    plugin_file = tmp_path / "alcove-search" / "alcove-search.php"
    readme_file = tmp_path / "alcove-search" / "readme.txt"
    css_file = tmp_path / "alcove-search" / "assets" / "alcove-search.css"

    assert zip_path.is_file()
    assert plugin_file.is_file()
    assert readme_file.is_file()
    assert css_file.is_file()
    assert "wrote WordPress plugin" in result.stdout

    plugin_contents = plugin_file.read_text(encoding="utf-8")
    assert "add_shortcode('alcove_search'" in plugin_contents
    assert "class Alcove_Search_Widget extends WP_Widget" in plugin_contents
    assert "Settings > Alcove Search" in readme_file.read_text(encoding="utf-8")

    with zipfile.ZipFile(zip_path) as archive:
        names = set(archive.namelist())

    assert "alcove-search/alcove-search.php" in names
    assert "alcove-search/readme.txt" in names
    assert "alcove-search/assets/alcove-search.css" in names
