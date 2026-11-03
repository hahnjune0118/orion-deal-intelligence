"""Original synthetic research cases; lazy exports keep world builders off ingestion imports."""
__all__=['generate_dataset','agent_visible_bundle','replay_scenario','validate_dataset']


def __getattr__(name):
    if name=='generate_dataset':
        from .generate import generate_dataset
        return generate_dataset
    if name=='agent_visible_bundle':
        from .load import agent_visible_bundle
        return agent_visible_bundle
    if name=='replay_scenario':
        from .scenario import replay_scenario
        return replay_scenario
    if name=='validate_dataset':
        from .validate import validate_dataset
        return validate_dataset
    raise AttributeError(name)
