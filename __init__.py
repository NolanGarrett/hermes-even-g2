"""Public plugin registration; importing the plugin has no network side effects."""
def register(ctx):
    from .even_g2.plugin import register as implementation
    return implementation(ctx)
