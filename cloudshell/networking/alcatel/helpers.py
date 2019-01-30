import re


def copy_additional_settings_files(system_action, path, dst):
    """Copy additional settings files that can be exists.

    :type system_action: cloudshell.networking.alcatel.command_actions.system_actions.SystemActions
    :type path: str
    :type dst: str
    """
    path = re.sub(r'\..{3}$', '', path)
    for ext in ('.sdx', '.ndx'):
        try:
            system_action.copy(path + ext, dst + ext)
        except Exception as e:
            # if we don't have these files just skip
            if 'Copy failed' in str(e):
                break
            else:
                raise e
