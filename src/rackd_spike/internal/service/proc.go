package service

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"sync"
	"syscall"
)

type ExecService struct {
	sync.RWMutex
	name   string
	t      int
	pid    int
	cmd    *exec.Cmd
	cmdStr string
	args   []string
}

func NewExecService(name string, t int, cmd string, args ...string) Service {
	return &ExecService{
		name:   name,
		t:      t,
		pid:    -1,
		cmdStr: cmd,
		args:   args,
	}
}

func (e *ExecService) Name() string {
	return e.name
}

func (e *ExecService) Type() int {
	return e.t
}

func (e *ExecService) PID() int {
	e.RLock()
	defer e.RUnlock()
	return e.pid
}

func (e *ExecService) Start(ctx context.Context) (err error) {
	e.Lock()
	defer e.Unlock()
	if e.pid != -1 && e.cmd != nil && !e.cmd.ProcessState.Exited() {
		return ErrServiceAlreadyRunning
	}
	defer func() {
		if err == nil {
			e.pid = e.cmd.Process.Pid
		}
	}()
	if e.cmd != nil && e.cmd.ProcessState.Exited() {
		err = e.cmd.Process.Release()
		if err != nil {
			return err
		}
	}
	e.cmd = exec.CommandContext(ctx, e.cmdStr, e.args...)
	return e.cmd.Start()
}

func (e *ExecService) Stop(ctx context.Context) (err error) {
	e.Lock()
	defer e.Unlock()
	if e.pid == -1 || e.cmd == nil || (e.cmd != nil && e.cmd.ProcessState != nil && e.cmd.ProcessState.Exited()) {
		return ErrServiceAlreadyStopped
	}
	defer func() {
		if err == nil {
			e.pid = -1
			e.cmd = nil
		}
	}()
	procExitChan := make(chan error)
	go func() {
		select {
		case <-ctx.Done():
			close(procExitChan)
			return
		case procExitChan <- e.cmd.Wait():
		}
	}()
	err = e.cmd.Process.Signal(syscall.SIGTERM)
	if err != nil {
		return err
	}
	select {
	case <-ctx.Done():
		err = e.cmd.Process.Kill()
		if err != nil {
			return err
		}
	case <-procExitChan:
		// TODO handle if SIGTERM caused the process to shutdown uncleanly
		return nil
	}
	return ctx.Err()
}

func (e *ExecService) Restart(ctx context.Context) (err error) {
	err = e.Stop(ctx)
	if err != nil {
		return err
	}
	return e.Start(ctx)
}

func (e *ExecService) Status(_ context.Context) error {
	e.RLock()
	defer e.RUnlock()
	if e.cmd.ProcessState != nil && (!e.cmd.ProcessState.Exited() || e.cmd.ProcessState.Success()) {
		return nil
	}
	return fmt.Errorf("%w: service exited: %d", ErrUnexpectedServiceExit, e.cmd.ProcessState.ExitCode())
}

type ReloadableExecService struct {
	ExecService
	ReloadSig os.Signal
}

func NewReloadableExecService(sig os.Signal, name string, t int, cmd string, args ...string) ReloadableService {
	return &ReloadableExecService{
		ExecService: ExecService{
			name:   name,
			t:      t,
			pid:    -1,
			cmdStr: cmd,
			args:   args,
		},
		ReloadSig: sig,
	}
}

func (r *ReloadableExecService) Reload(_ context.Context) error {
	r.RLock()
	defer r.RUnlock()
	return r.cmd.Process.Signal(r.ReloadSig)
}
