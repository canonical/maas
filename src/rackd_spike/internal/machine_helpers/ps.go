package machinehelpers

import (
	"bufio"
	"context"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
)

const (
	vertCheckExec = "systemd-detect-virt"
)

var (
	vertCheckArgs = []string{"-c"}
)

func RunningInContainer(ctx context.Context) (bool, error) {
	cmd := exec.CommandContext(ctx, vertCheckExec, vertCheckArgs...)
	if err := cmd.Run(); err != nil {
		if cmd.ProcessState.ExitCode() == 1 {
			return false, nil
		}
		return false, err
	}
	return true, nil
}

func PIDInContainer(pid int, procPath string) (bool, error) {
	if len(procPath) == 0 {
		procPath = "/proc"
	}
	cgroupPath := filepath.Join(procPath, strconv.Itoa(pid), "cgroup")
	f, err := os.Open(cgroupPath)
	if err != nil {
		return false, err
	}
	defer f.Close()
	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		line := scanner.Text()
		cgroup := strings.SplitN(line, ":", 2)
		// cgroup[2] will be the cgroup heirarchy
		if strings.HasPrefix(cgroup[2], "/lxc") || strings.Contains(cgroup[2], "docker") {
			return true, nil
		}
	}
	return false, nil
}

func GetRunningPIDsWithCMD(ctx context.Context, command, procPath string, excludeContainerProcesses bool) ([]int, error) {
	if len(procPath) == 0 {
		procPath = "/proc"
	}
	dirs, err := os.ReadDir(procPath)
	if err != nil {
		return nil, err
	}
	var runningPIDs []int
	runningInContainer, err := RunningInContainer(ctx)
	if err != nil {
		return nil, err
	}
	for _, dir := range dirs {
		pid, parseErr := strconv.Atoi(dir.Name())
		if parseErr == nil {
			pidInContainer, err := PIDInContainer(pid, procPath)
			if err != nil {
				return nil, err
			}
			if excludeContainerProcesses && !runningInContainer && pidInContainer {
				continue
			}
			runningPIDs = append(runningPIDs, pid)
		}
	}
	return runningPIDs, nil
}
