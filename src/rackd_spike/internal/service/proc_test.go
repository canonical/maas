package service

import (
	"context"
	"errors"
	"testing"
)

const testProc = "/usr/bin/yes"

func TestExecService(t *testing.T) {
	table := []struct {
		Name string
		In   struct {
			Name string
			Type int
			Cmd  string
			Args []string
		}
		Out        error
		CleanupOut error
		Action     string
		Cleanup    string
	}{{
		Name: "start_new_service",
		In: struct {
			Name string
			Type int
			Cmd  string
			Args []string
		}{
			Name: "mysvc",
			Type: SvcDHCP,
			Cmd:  testProc,
			Args: []string{"hello"},
		},
		Action:  "start",
		Cleanup: "stop",
	}}
	for _, tcase := range table {
		t.Run(tcase.Name, func(tt *testing.T) {
			svc := NewExecService(tcase.In.Name, tcase.In.Type, tcase.In.Cmd, tcase.In.Args...)
			ctx := context.Background()
			var err error
			switch tcase.Action {
			case "start":
				err = svc.Start(ctx)
			case "stop":
				err = svc.Stop(ctx)
			case "restart":
				err = svc.Restart(ctx)
			}
			if !errors.Is(err, tcase.Out) {
				tt.Fatalf("expected %v to equal %v", err, tcase.Out)
			}
			switch tcase.Cleanup {
			case "stop":
				err = svc.Stop(ctx)
			default:
				return
			}
			if !errors.Is(err, tcase.CleanupOut) {
				tt.Fatalf("expectd %v to equal %v", err, tcase.CleanupOut)
			}
		})
	}
}
