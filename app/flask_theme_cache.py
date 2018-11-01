import jinja2
import flask_themes2

_cache = {}


def get_global_theme_template():
    def _get_templatepath(theme, templatename, fallback):
        cache_key = '{}{}{}'.format(theme, templatename, fallback)
        path = _cache.get(cache_key)

        if not path:
            templatepath = '_themes/{}/{}'.format(theme, templatename)

            if (not fallback) or flask_themes2.template_exists(templatepath):
                path = templatepath
            else:
                path = templatename

            _cache[cache_key] = path

        return path

    @jinja2.contextfunction
    def global_theme_template(ctx, templatename, fallback=True):
        theme = flask_themes2.active_theme(ctx)
        return _get_templatepath(theme, templatename, fallback)

    return global_theme_template


def clear():
    _cache.clear()
