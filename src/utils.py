import psutil

# cvt_status = lambda is_alive: 'alive' if is_alive == 'running' else 'dead'

def check_ps_status(parent_pid, including_parent=True):
    status = {}
    parent = psutil.Process(parent_pid)
    for idx, child in enumerate(parent.children(recursive=True)):
        status[f'child-{idx}'] = {'pid': child.pid, 'status': child.status()}
        print(child.name)
    if including_parent:
        status['parent'] = {'pid': parent.pid, 'status': parent.status()} 
    return status
        