package service

import (
	"context"
	"errors"
	"testing"
)

type MockService struct {
	Service
	pid        int
	name       string
	t          int
	startErr   error
	stopErr    error
	restartErr error
}

func (m MockService) Name() string {
	return m.name
}

func (m MockService) PID() int {
	return m.pid
}

func (m MockService) Type() int {
	return m.t
}

func (m MockService) Start(ctx context.Context) error {
	return m.startErr
}

func (m MockService) Stop(ctx context.Context) error {
	return m.stopErr
}

func (m MockService) Restart(ctx context.Context) error {
	return m.restartErr
}

func TestSupvisor(t *testing.T) {
	table := []struct {
		Name   string
		In     Service
		Out    error
		Action string
	}{{
		Name: "start_new_valid_service",
		In: MockService{
			pid:  -1,
			name: "mysvc",
			t:    SvcDHCP,
		},
		Action: "start",
	}, {
		Name: "start_all_new_valid_service",
		In: MockService{
			pid:  -1,
			name: "mysvc",
			t:    SvcDHCP,
		},
		Action: "start_all",
	}, {
		Name: "start_type_new_valid_service",
		In: MockService{
			pid:  -1,
			name: "mysvc",
			t:    SvcDHCP,
		},
		Action: "start_type",
	}, {
		Name: "start_started_service",
		In: MockService{
			pid:  1,
			name: "mysvc",
			t:    SvcDHCP,
		},
		Out:    ErrServiceAlreadyRunning,
		Action: "start",
	}, {
		Name: "stop_started_service",
		In: MockService{
			pid:  1,
			name: "mysvc",
			t:    SvcDHCP,
		},
		Action: "stop",
	}, {
		Name: "stop_stopped_service",
		In: MockService{
			pid:  -1,
			name: "mysvc",
			t:    SvcDHCP,
		},
		Out:    ErrServiceAlreadyStopped,
		Action: "stop",
	}, {
		Name: "stop_type_started_service",
		In: MockService{
			pid:  1,
			name: "mysvc",
			t:    SvcDHCP,
		},
		Action: "stop_type",
	}, {
		Name: "stop_all_started_service",
		In: MockService{
			pid:  1,
			name: "mysvc",
			t:    SvcDHCP,
		},
		Action: "stop_all",
	}, {
		Name: "restart_started_service",
		In: MockService{
			pid:  1,
			name: "mysvc",
			t:    SvcDHCP,
		},
		Action: "restart",
	}, {
		Name: "restart_stopped_service",
		In: MockService{
			pid:  -1,
			name: "mysvc",
			t:    SvcDHCP,
		},
		Out:    ErrInvalidServiceState,
		Action: "restart",
	}, {
		Name: "restart_by_type_started_service",
		In: MockService{
			pid:  1,
			name: "mysvc",
			t:    SvcDHCP,
		},
		Action: "restart_by_type",
	}}
	for _, tcase := range table {
		t.Run(tcase.Name, func(tt *testing.T) {
			sup := NewSupervisor()
			sup.RegisterService(tcase.In)
			ctx := context.Background()
			var err error
			switch tcase.Action {
			case "start_all":
				err = sup.StartAll(ctx)
			case "start":
				err = sup.Start(ctx, tcase.In.Name())
			case "start_by_type":
				err = sup.StartByType(ctx, tcase.In.Type())
			case "stop_all":
				err = sup.StopAll(ctx)
			case "stop":
				err = sup.Stop(ctx, tcase.In.Name())
			case "stop_by_type":
				err = sup.StopByType(ctx, tcase.In.Type())
			case "restart":
				err = sup.Restart(ctx, tcase.In.Name())
			case "restart_by_type":
				err = sup.RestartByType(ctx, tcase.In.Type())
			}
			if !errors.Is(err, tcase.Out) {
				tt.Fatalf("expected %v to equal %v", err, tcase.Out)
			}
		})
	}
}
