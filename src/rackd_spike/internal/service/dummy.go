package service

import (
	"context"
	"os"
)

type DummySvc struct {
	name string
}

func NewDummy(name string) Service {
	return &DummySvc{name: name}
}

func (r *DummySvc) Name() string {
	return r.name

}
func (r *DummySvc) Type() int {
	return SvcRack
}

func (r *DummySvc) PID() int {
	return os.Getpid()
}

func (r *DummySvc) Start(context.Context) error {
	return nil
}

func (r *DummySvc) Stop(context.Context) error {
	return nil
}

func (r *DummySvc) Restart(context.Context) error {
	return nil
}

func (r *DummySvc) Status(context.Context) error {
	return nil
}
