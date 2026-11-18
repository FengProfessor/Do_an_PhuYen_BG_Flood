"""
Cập nhật forcing tại mỗi bước thời gian.

Hiện tại hỗ trợ:
- Uniform forcing (rain, wind, atmp)
- Spatial rainfall (multi-station) được xử lý trong updateforcing.py
"""


def update_forcing(param, loop, forcing):
    """
    Cập nhật giá trị forcing cho bước thời gian hiện tại.

    Hiện tại: placeholder sẽ implement đầy đủ khi cần
    rain/wind/atmp forcing.
    """
    # Rain
    if forcing.Rain.inputfile:
        _forcing_this_step_uniform(loop, forcing.Rain)

    # Atmospheric pressure
    if forcing.Atmp.inputfile:
        _forcing_this_step_uniform(loop, forcing.Atmp)

    # Wind
    if forcing.UWind.inputfile:
        _forcing_this_step_uniform(loop, forcing.UWind)
        _forcing_this_step_uniform(loop, forcing.VWind)


def _forcing_this_step_uniform(loop, dynforcing):
    """
    Nội suy giá trị uniform forcing tại thời điểm hiện tại.
    """
    if not hasattr(dynforcing, 'uniform') or dynforcing.uniform != 1:
        return
    if not hasattr(dynforcing, 'unidata') or not dynforcing.unidata:
        return

    from .utils import interptime

    if len(dynforcing.unidata) == 1:
        dynforcing.nowvalue = dynforcing.unidata[0].wspeed
        return

    if loop.totaltime <= dynforcing.unidata[0].time:
        step = 1
    elif loop.totaltime >= dynforcing.unidata[-1].time:
        step = len(dynforcing.unidata) - 1
    else:
        step = 1
        while step < len(dynforcing.unidata) - 1 and \
              dynforcing.unidata[step].time < loop.totaltime:
            step += 1

    dt_f = dynforcing.unidata[step].time - dynforcing.unidata[step - 1].time
    t_el = loop.totaltime - dynforcing.unidata[step - 1].time

    dynforcing.nowvalue = interptime(
        dynforcing.unidata[step].wspeed,
        dynforcing.unidata[step - 1].wspeed,
        dt_f, t_el
    )
