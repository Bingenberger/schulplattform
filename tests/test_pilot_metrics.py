"""Numeric/safety contracts for local resource measurements, independent of Docker."""
from pathlib import Path
import pytest
from scripts.pilot_metrics import (meminfo,pairs,pressure,cgroup_path,cpu_delta,
 host_cpu_delta,identities_unchanged,totals,summarize)

def test_memory_views_are_separate_and_not_double_counted():
    services={"a":{"memoryCurrentBytes":100,"memoryAnonBytes":40,"memoryFileBytes":50,
       "workingSetApproxBytes":80,"cpuDelta":{"cores":.5}},
       "b":{"memoryCurrentBytes":80,"memoryAnonBytes":50,"memoryFileBytes":20,
       "workingSetApproxBytes":70,"cpuDelta":{"cores":1}}}
    result=totals(services)
    assert result=={"memoryCurrentBytes":180,"memoryAnonBytes":90,"memoryFileBytes":70,
                   "workingSetApproxBytes":150,"cpuCores":1.5}

def test_cpu_uses_one_core_as_100_percent_and_rejects_counter_reset():
    assert cpu_delta({"usage_usec":100},{"usage_usec":2_000_100},2)=={"cores":1}
    with pytest.raises(ValueError,match="reset"):
        cpu_delta({"usage_usec":100},{"usage_usec":90},1)

def test_host_cpu_separates_iowait_and_steal():
    before={key:0 for key in ("user","nice","system","idle","iowait","irq","softirq","steal")}
    after=before|{"user":20,"idle":60,"iowait":15,"steal":5}
    assert host_cpu_delta(before,after)=={"busyPercent":25,"iowaitPercent":15,"stealPercent":5}

def test_kernel_values_keep_bytes_and_stall_counters():
    assert meminfo("MemTotal: 100 kB\nSwapFree: 5 kB\nUnknown: 9 kB")=={"MemTotalBytes":102400,"SwapFreeBytes":5120}
    assert pressure("some avg10=0.00 avg60=1.50 avg300=2.00 total=300\n")["some"]["total"]==300
    with pytest.raises(ValueError):pairs("oom -1")

def test_cgroup_cannot_escape_root_through_parent_or_symlink(tmp_path):
    assert cgroup_path("0::/system.slice/docker.scope",tmp_path)==tmp_path/"system.slice/docker.scope"
    with pytest.raises(ValueError):cgroup_path("0::/../../etc",tmp_path)
    (tmp_path/"escape").symlink_to("/tmp")
    with pytest.raises(ValueError):cgroup_path("0::/escape",tmp_path)
    with pytest.raises(ValueError):cgroup_path("1:memory:/old-controller",tmp_path)

@pytest.mark.parametrize("change",[{"pid":2},{"startedAt":"later"},{"running":False},{"restartCount":1}])
def test_restart_detection_includes_manual_restart_without_docker_counter(change):
    state={"cid":{"pid":1,"startedAt":"start","running":True,"image":"image","restartCount":0}}
    assert not identities_unchanged(state,{"cid":state["cid"]|change})

def test_summary_keeps_oom_and_io_deltas_and_aggregate_peak():
    points=[]
    for index in (0,1):
        service={"memoryCurrentBytes":100+index*20,"memoryAnonBytes":50,"memoryFileBytes":40,
           "workingSetApproxBytes":80,"memoryEvents":{"oom":index,"oom_kill":index},
           "state":{"restartCount":0},"io":{"8:0":{"rbytes":index*1024,"wbytes":index*2048}},
           "cpu":{"throttled_usec":index*4}}
        if index:service["cpuDelta"]={"cores":.5}
        points.append({"services":{"app":service},"totals":totals({"app":service}),"elapsedSeconds":index*5})
    result=summarize(points)
    assert result["aggregate"]["memoryCurrentMaxBytes"]==120
    assert result["aggregate"]["oomKillsDelta"]==1
    assert result["services"]["app"]["ioBytesDelta"]=={"rbytes":1024,"wbytes":2048}
    assert result["observedSeconds"]==5


def test_missing_probe_is_unknown_not_an_empty_queue():
    from scripts.pilot_metrics import workload_summary
    samples=[{"workloads":{"abgen/pdf":{"unavailable":True},
       "losverkauf/app":{},"kompetenz-manager/worker":{"unmailedNotificationRows":3}}}]
    assert workload_summary(samples)=={"abgenPdfActiveSamples":None,"losverkaufPendingMax":0,
                                      "kompetenzUnmailedMax":3}
