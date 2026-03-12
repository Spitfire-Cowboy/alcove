"""Export an installable WordPress plugin for Alcove search."""

from __future__ import annotations

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from alcove import __version__

PLUGIN_SLUG = "alcove-search"
PLUGIN_DIRNAME = PLUGIN_SLUG
PLUGIN_MAIN_FILE = f"{PLUGIN_SLUG}.php"
PLUGIN_ZIP_NAME = "alcove-search-wordpress.zip"


def export_wordpress_plugin(output_dir: str | Path) -> Path:
    """Write the WordPress plugin directory and ZIP archive."""
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)

    plugin_root = destination / PLUGIN_DIRNAME
    assets_dir = plugin_root / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    files = {
        plugin_root / PLUGIN_MAIN_FILE: _plugin_php(),
        plugin_root / "readme.txt": _plugin_readme(),
        assets_dir / "alcove-search.css": _plugin_css(),
    }
    for path, content in files.items():
        path.write_text(content, encoding="utf-8")

    zip_path = destination / PLUGIN_ZIP_NAME
    with ZipFile(zip_path, "w", compression=ZIP_DEFLATED) as archive:
        for path in sorted(plugin_root.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(destination))

    return zip_path


def _plugin_php() -> str:
    template = """<?php
/**
 * Plugin Name: Alcove Search
 * Plugin URI: https://github.com/Pro777/alcove
 * Description: Embed Alcove local-first search as a shortcode or widget.
 * Version: __VERSION__
 * Requires at least: 6.0
 * Requires PHP: 7.4
 * Author: John Malone
 * License: Apache-2.0
 * License URI: https://www.apache.org/licenses/LICENSE-2.0
 * Text Domain: alcove-search
 */

if (!defined('ABSPATH')) {
    exit;
}

final class Alcove_Search_Plugin {
    const OPTION_API_BASE = 'alcove_search_api_base';
    const OPTION_DEFAULT_RESULTS = 'alcove_search_default_results';
    const NONCE_ACTION = 'alcove_search_form';
    const QUERY_PARAM = 'alcove_search_q';
    const LIMIT_PARAM = 'alcove_search_k';

    public static function boot() {
        add_shortcode('alcove_search', array(__CLASS__, 'render_shortcode'));
        add_action('widgets_init', array(__CLASS__, 'register_widget'));
        add_action('admin_init', array(__CLASS__, 'register_settings'));
        add_action('admin_menu', array(__CLASS__, 'register_settings_page'));
        add_action('wp_enqueue_scripts', array(__CLASS__, 'enqueue_assets'));
    }

    public static function enqueue_assets() {
        wp_register_style(
            'alcove-search',
            plugins_url('assets/alcove-search.css', __FILE__),
            array(),
            '__VERSION__'
        );
        wp_enqueue_style('alcove-search');
    }

    public static function register_widget() {
        register_widget('Alcove_Search_Widget');
    }

    public static function register_settings() {
        register_setting(
            'alcove_search_settings',
            self::OPTION_API_BASE,
            array(
                'type' => 'string',
                'sanitize_callback' => 'esc_url_raw',
                'default' => 'http://127.0.0.1:8000',
            )
        );
        register_setting(
            'alcove_search_settings',
            self::OPTION_DEFAULT_RESULTS,
            array(
                'type' => 'integer',
                'sanitize_callback' => array(__CLASS__, 'sanitize_results_limit'),
                'default' => 5,
            )
        );

        add_settings_section(
            'alcove_search_main',
            'Connection settings',
            '__return_false',
            'alcove-search'
        );

        add_settings_field(
            self::OPTION_API_BASE,
            'Alcove API base URL',
            array(__CLASS__, 'render_api_base_field'),
            'alcove-search',
            'alcove_search_main'
        );
        add_settings_field(
            self::OPTION_DEFAULT_RESULTS,
            'Default result count',
            array(__CLASS__, 'render_results_field'),
            'alcove-search',
            'alcove_search_main'
        );
    }

    public static function sanitize_results_limit($value) {
        $value = absint($value);
        if ($value < 1) {
            return 5;
        }
        return min($value, 20);
    }

    public static function register_settings_page() {
        add_options_page(
            'Alcove Search',
            'Alcove Search',
            'manage_options',
            'alcove-search',
            array(__CLASS__, 'render_settings_page')
        );
    }

    public static function render_api_base_field() {
        $value = esc_attr(self::api_base());
        echo '<input type="url" class="regular-text code" name="' . esc_attr(self::OPTION_API_BASE) . '" value="' . $value . '" />';
        echo '<p class="description">Example: http://127.0.0.1:8000</p>';
    }

    public static function render_results_field() {
        $value = absint(get_option(self::OPTION_DEFAULT_RESULTS, 5));
        echo '<input type="number" min="1" max="20" name="' . esc_attr(self::OPTION_DEFAULT_RESULTS) . '" value="' . esc_attr((string) $value) . '" />';
    }

    public static function render_settings_page() {
        if (!current_user_can('manage_options')) {
            return;
        }
        ?>
        <div class="wrap">
            <h1>Alcove Search</h1>
            <p>Configure the Alcove API endpoint used by the shortcode and widget.</p>
            <form action="options.php" method="post">
                <?php
                settings_fields('alcove_search_settings');
                do_settings_sections('alcove-search');
                submit_button();
                ?>
            </form>
            <p>Shortcode: <code>[alcove_search]</code></p>
        </div>
        <?php
    }

    public static function render_shortcode($atts = array()) {
        $atts = shortcode_atts(
            array(
                'title' => 'Search the archive',
                'placeholder' => 'Ask Alcove',
                'button_label' => 'Search',
                'results' => get_option(self::OPTION_DEFAULT_RESULTS, 5),
                'show_scores' => 'true',
                'api_base' => '',
            ),
            $atts,
            'alcove_search'
        );

        return self::render_interface($atts, 'shortcode');
    }

    public static function render_interface($args, $context = 'widget') {
        $args = wp_parse_args(
            $args,
            array(
                'title' => 'Search the archive',
                'placeholder' => 'Ask Alcove',
                'button_label' => 'Search',
                'results' => get_option(self::OPTION_DEFAULT_RESULTS, 5),
                'show_scores' => true,
                'api_base' => '',
            )
        );
        $limit = self::sanitize_results_limit($args['results']);
        $query = isset($_GET[self::QUERY_PARAM]) ? sanitize_text_field(wp_unslash($_GET[self::QUERY_PARAM])) : '';
        $submitted_limit = isset($_GET[self::LIMIT_PARAM]) ? self::sanitize_results_limit(wp_unslash($_GET[self::LIMIT_PARAM])) : $limit;
        $results = null;
        $error = '';
        if ($query !== '') {
            $response = self::perform_search($query, $submitted_limit, $args['api_base']);
            $results = $response['results'];
            $error = $response['error'];
        }

        ob_start();
        ?>
        <div class="alcove-search alcove-search-<?php echo esc_attr($context); ?>">
            <?php if (!empty($args['title'])) : ?>
                <h3 class="alcove-search__title"><?php echo esc_html($args['title']); ?></h3>
            <?php endif; ?>
            <form class="alcove-search__form" method="get">
                <label class="screen-reader-text" for="alcove-search-q"><?php echo esc_html($args['placeholder']); ?></label>
                <input
                    id="alcove-search-q"
                    class="alcove-search__input"
                    type="search"
                    name="<?php echo esc_attr(self::QUERY_PARAM); ?>"
                    value="<?php echo esc_attr($query); ?>"
                    placeholder="<?php echo esc_attr($args['placeholder']); ?>"
                />
                <input type="hidden" name="<?php echo esc_attr(self::LIMIT_PARAM); ?>" value="<?php echo esc_attr((string) $submitted_limit); ?>" />
                <?php wp_nonce_field(self::NONCE_ACTION, '_alcove_nonce'); ?>
                <button class="alcove-search__button" type="submit"><?php echo esc_html($args['button_label']); ?></button>
            </form>
            <?php if ($error !== '') : ?>
                <p class="alcove-search__message alcove-search__message-error"><?php echo esc_html($error); ?></p>
            <?php elseif (is_array($results)) : ?>
                <?php if (empty($results)) : ?>
                    <p class="alcove-search__message">No matching results.</p>
                <?php else : ?>
                    <ol class="alcove-search__results">
                        <?php foreach ($results as $item) : ?>
                            <li class="alcove-search__result">
                                <p class="alcove-search__snippet"><?php echo esc_html($item['text']); ?></p>
                                <p class="alcove-search__meta">
                                    <span class="alcove-search__source"><?php echo esc_html($item['source']); ?></span>
                                    <?php if (filter_var($args['show_scores'], FILTER_VALIDATE_BOOLEAN)) : ?>
                                        <span class="alcove-search__score">Score: <?php echo esc_html($item['score']); ?></span>
                                    <?php endif; ?>
                                </p>
                            </li>
                        <?php endforeach; ?>
                    </ol>
                <?php endif; ?>
            <?php endif; ?>
        </div>
        <?php
        return (string) ob_get_clean();
    }

    public static function perform_search($query, $limit, $api_base = '') {
        if (
            !isset($_GET['_alcove_nonce']) ||
            !wp_verify_nonce(sanitize_text_field(wp_unslash($_GET['_alcove_nonce'])), self::NONCE_ACTION)
        ) {
            return array('results' => array(), 'error' => 'Search request rejected. Refresh the page and try again.');
        }

        $base = $api_base !== '' ? esc_url_raw($api_base) : self::api_base();
        if ($base === '') {
            return array('results' => array(), 'error' => 'Alcove API base URL is not configured.');
        }

        $response = wp_remote_post(
            trailingslashit($base) . 'query',
            array(
                'timeout' => 10,
                'headers' => array('Content-Type' => 'application/json'),
                'body' => wp_json_encode(
                    array(
                        'query' => $query,
                        'k' => $limit,
                    )
                ),
            )
        );

        if (is_wp_error($response)) {
            return array('results' => array(), 'error' => $response->get_error_message());
        }

        $code = wp_remote_retrieve_response_code($response);
        if ($code < 200 || $code >= 300) {
            return array('results' => array(), 'error' => 'Alcove API returned HTTP ' . intval($code) . '.');
        }

        $payload = json_decode(wp_remote_retrieve_body($response), true);
        if (!is_array($payload)) {
            return array('results' => array(), 'error' => 'Alcove API returned an invalid response.');
        }

        return array('results' => self::normalize_results($payload), 'error' => '');
    }

    public static function normalize_results($payload) {
        $documents = isset($payload['documents'][0]) && is_array($payload['documents'][0]) ? $payload['documents'][0] : array();
        $metadatas = isset($payload['metadatas'][0]) && is_array($payload['metadatas'][0]) ? $payload['metadatas'][0] : array();
        $distances = isset($payload['distances'][0]) && is_array($payload['distances'][0]) ? $payload['distances'][0] : array();
        $normalized = array();

        foreach ($documents as $index => $document) {
            $meta = isset($metadatas[$index]) && is_array($metadatas[$index]) ? $metadatas[$index] : array();
            $distance = isset($distances[$index]) ? floatval($distances[$index]) : 1.0;
            $score = $distance <= 1 ? number_format(1 - $distance, 3) : number_format($distance, 3);
            $normalized[] = array(
                'text' => wp_trim_words(wp_strip_all_tags((string) $document), 40, '...'),
                'source' => isset($meta['source']) ? (string) $meta['source'] : 'unknown',
                'score' => $score,
            );
        }

        return $normalized;
    }

    public static function api_base() {
        $value = trim((string) get_option(self::OPTION_API_BASE, 'http://127.0.0.1:8000'));
        return untrailingslashit($value);
    }
}

class Alcove_Search_Widget extends WP_Widget {
    public function __construct() {
        parent::__construct(
            'alcove_search_widget',
            'Alcove Search',
            array('description' => 'Search an Alcove index from a sidebar or footer.')
        );
    }

    public function widget($args, $instance) {
        echo $args['before_widget'];
        echo Alcove_Search_Plugin::render_interface(
            array(
                'title' => !empty($instance['title']) ? $instance['title'] : 'Search the archive',
                'placeholder' => !empty($instance['placeholder']) ? $instance['placeholder'] : 'Ask Alcove',
                'button_label' => !empty($instance['button_label']) ? $instance['button_label'] : 'Search',
                'results' => !empty($instance['results']) ? absint($instance['results']) : get_option(Alcove_Search_Plugin::OPTION_DEFAULT_RESULTS, 5),
                'show_scores' => !empty($instance['show_scores']),
            ),
            'widget'
        );
        echo $args['after_widget'];
    }

    public function form($instance) {
        $title = isset($instance['title']) ? $instance['title'] : 'Search the archive';
        $placeholder = isset($instance['placeholder']) ? $instance['placeholder'] : 'Ask Alcove';
        $button_label = isset($instance['button_label']) ? $instance['button_label'] : 'Search';
        $results = isset($instance['results']) ? absint($instance['results']) : 5;
        $show_scores = !empty($instance['show_scores']);
        ?>
        <p>
            <label for="<?php echo esc_attr($this->get_field_id('title')); ?>">Title</label>
            <input class="widefat" id="<?php echo esc_attr($this->get_field_id('title')); ?>" name="<?php echo esc_attr($this->get_field_name('title')); ?>" type="text" value="<?php echo esc_attr($title); ?>" />
        </p>
        <p>
            <label for="<?php echo esc_attr($this->get_field_id('placeholder')); ?>">Placeholder</label>
            <input class="widefat" id="<?php echo esc_attr($this->get_field_id('placeholder')); ?>" name="<?php echo esc_attr($this->get_field_name('placeholder')); ?>" type="text" value="<?php echo esc_attr($placeholder); ?>" />
        </p>
        <p>
            <label for="<?php echo esc_attr($this->get_field_id('button_label')); ?>">Button label</label>
            <input class="widefat" id="<?php echo esc_attr($this->get_field_id('button_label')); ?>" name="<?php echo esc_attr($this->get_field_name('button_label')); ?>" type="text" value="<?php echo esc_attr($button_label); ?>" />
        </p>
        <p>
            <label for="<?php echo esc_attr($this->get_field_id('results')); ?>">Result count</label>
            <input class="tiny-text" id="<?php echo esc_attr($this->get_field_id('results')); ?>" name="<?php echo esc_attr($this->get_field_name('results')); ?>" type="number" min="1" max="20" value="<?php echo esc_attr((string) $results); ?>" />
        </p>
        <p>
            <input class="checkbox" id="<?php echo esc_attr($this->get_field_id('show_scores')); ?>" name="<?php echo esc_attr($this->get_field_name('show_scores')); ?>" type="checkbox" <?php checked($show_scores); ?> />
            <label for="<?php echo esc_attr($this->get_field_id('show_scores')); ?>">Show similarity scores</label>
        </p>
        <?php
    }

    public function update($new_instance, $old_instance) {
        return array(
            'title' => sanitize_text_field($new_instance['title'] ?? ''),
            'placeholder' => sanitize_text_field($new_instance['placeholder'] ?? ''),
            'button_label' => sanitize_text_field($new_instance['button_label'] ?? ''),
            'results' => Alcove_Search_Plugin::sanitize_results_limit($new_instance['results'] ?? 5),
            'show_scores' => !empty($new_instance['show_scores']) ? 1 : 0,
        );
    }
}

Alcove_Search_Plugin::boot();
"""
    return template.replace("__VERSION__", __version__)


def _plugin_css() -> str:
    return """\
.alcove-search {
  border: 1px solid #d7ddd4;
  border-radius: 12px;
  padding: 1rem;
  background: #f7f6f1;
}

.alcove-search__title {
  margin: 0 0 0.75rem;
  font-size: 1.1rem;
}

.alcove-search__form {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.alcove-search__input {
  flex: 1 1 16rem;
  min-width: 0;
}

.alcove-search__button {
  border: 0;
  border-radius: 999px;
  padding: 0.7rem 1rem;
  background: #1d4938;
  color: #fff;
  cursor: pointer;
}

.alcove-search__results {
  margin: 1rem 0 0;
  padding-left: 1.2rem;
}

.alcove-search__result + .alcove-search__result {
  margin-top: 0.9rem;
}

.alcove-search__snippet,
.alcove-search__meta,
.alcove-search__message {
  margin: 0;
}

.alcove-search__meta {
  display: flex;
  gap: 0.75rem;
  margin-top: 0.25rem;
  color: #4d5b52;
  font-size: 0.92rem;
}

.alcove-search__message-error {
  color: #8a1f11;
}
"""


def _plugin_readme() -> str:
    return """=== Alcove Search ===
Contributors: pro777
Tags: search, widget, shortcode, local search
Requires at least: 6.0
Tested up to: 6.8
Requires PHP: 7.4
Stable tag: 0.3.0
License: Apache-2.0
License URI: https://www.apache.org/licenses/LICENSE-2.0

Expose an Alcove search index as a WordPress shortcode or classic widget.

== Description ==

The plugin connects a WordPress site to an Alcove server by posting to the `/query`
endpoint. Configure the Alcove API base URL under Settings > Alcove Search.

Shortcode example:

[alcove_search title="Search the archive" results="5" show_scores="true"]

== Installation ==

1. Upload the ZIP generated by `alcove wordpress-plugin`.
2. Activate the plugin in WordPress.
3. Set the Alcove API base URL under Settings > Alcove Search.
4. Add the shortcode or the Alcove Search widget to your site.
"""
