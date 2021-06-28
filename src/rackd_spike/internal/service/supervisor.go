package service

import (
	"context"
	"errors"
	"sync"
)

const (
	SvcUnknown = iota
	SvcDHCP
	SvcDNS
	SvcNTP
	SvcPROXY
)

var (
	ErrUnknownService        = errors.New("service is not registered with supervisor")
	ErrServiceAlreadyRunning = errors.New("service is already in a running state")
	ErrServiceAlreadyStopped = errors.New("service is already in a stopped state")
	ErrInvalidServiceState   = errors.New("service is in an invalid state for this operation")
	ErrUnexpectedServiceExit = errors.New("service exited unexpectedly")
)

type Service interface {
	Name() string
	Type() int
	PID() int
	Start(context.Context) error
	Stop(context.Context) error
	Restart(context.Context) error
	Status(context.Context) error
}

type ReloadableService interface {
	Service
	Reload(context.Context) error
}

type SvcManager interface {
	RegisterService(Service)
	StartAll(context.Context) error
	Start(context.Context, string) error
	StartByType(context.Context, int) error
	StopAll(context.Context) error
	Stop(context.Context, string) error
	StopByType(context.Context, int) error
	Restart(context.Context, string) error
	RestartByType(context.Context, int) error
	Get(string) (Service, error)
	GetType(int) ([]Service, error)
	GetPID(int) (Service, error)
}

type Supervisor struct {
	sync.RWMutex
	procsByPID  map[int]Service
	procsByName map[string]Service
	procsByType map[int][]Service
}

func NewSupervisor() *Supervisor {
	return &Supervisor{
		procsByPID:  make(map[int]Service),
		procsByName: make(map[string]Service),
		procsByType: make(map[int][]Service),
	}
}

func (s *Supervisor) RegisterService(svc Service) {
	s.procsByName[svc.Name()] = svc
	svcs := s.procsByType[svc.Type()]
	s.procsByType[svc.Type()] = append(svcs, svc)
	if pid := svc.PID(); pid != -1 {
		s.procsByPID[pid] = svc
	}
}

func (s *Supervisor) StartAll(ctx context.Context) error {
	for _, svc := range s.procsByName {
		err := svc.Start(ctx)
		if err != nil {
			return err
		}
	}
	return nil
}

func (s *Supervisor) StopAll(ctx context.Context) error {
	for _, svc := range s.procsByPID {
		err := svc.Stop(ctx)
		if err != nil {
			return err
		}
	}
	return nil
}

func (s *Supervisor) Start(ctx context.Context, name string) (err error) {
	svc, err := s.Get(name)
	if err != nil {
		return err
	}
	pid := svc.PID()
	if _, err = s.GetByPID(pid); err == nil || pid != -1 {
		return ErrServiceAlreadyRunning
	}
	defer func() {
		if err == nil {
			s.Lock()
			defer s.Unlock()
			s.procsByPID[svc.PID()] = svc
		}
	}()
	return svc.Start(ctx)
}

func (s *Supervisor) StartByType(ctx context.Context, t int) error {
	svcs, err := s.GetByType(t)
	if err != nil {
		return err
	}
	for _, svc := range svcs {
		err = s.Start(ctx, svc.Name())
		if err != nil {
			return err
		}
	}
	return nil
}

func (s *Supervisor) Stop(ctx context.Context, name string) (err error) {
	svc, err := s.Get(name)
	if err != nil {
		return err
	}
	pid := svc.PID()
	if _, err = s.GetByPID(svc.PID()); err != nil || pid == -1 {
		return ErrServiceAlreadyStopped
	}
	defer func() {
		if err == nil {
			s.Lock()
			defer s.Unlock()
			delete(s.procsByPID, pid)
		}
	}()
	return svc.Stop(ctx)
}

func (s *Supervisor) StopByType(ctx context.Context, t int) error {
	svcs, err := s.GetByType(t)
	if err != nil {
		return err
	}
	for _, svc := range svcs {
		err = s.Stop(ctx, svc.Name())
		if err != nil {
			return err
		}
	}
	return nil
}

func (s *Supervisor) Restart(ctx context.Context, name string) (err error) {
	svc, err := s.Get(name)
	if err != nil {
		return err
	}
	pid := svc.PID()
	if _, hasPID := s.procsByPID[pid]; !hasPID || pid == -1 {
		return ErrInvalidServiceState
	}
	defer func() {
		if err == nil {
			s.Lock()
			defer s.Unlock()
			// Restart should change PIDs
			delete(s.procsByPID, pid)
			s.procsByPID[svc.PID()] = svc
		}
	}()
	return svc.Restart(ctx)
}

func (s *Supervisor) RestartByType(ctx context.Context, t int) error {
	svcs, err := s.GetByType(t)
	if err != nil {
		return err
	}
	for _, svc := range svcs {
		err = s.Restart(ctx, svc.Name())
		if err != nil {
			return err
		}
	}
	return nil
}

func (s *Supervisor) Get(name string) (Service, error) {
	s.RLock()
	defer s.RUnlock()
	if svc, ok := s.procsByName[name]; ok {
		return svc, nil
	}
	return nil, ErrUnknownService
}

func (s *Supervisor) GetByType(t int) ([]Service, error) {
	s.RLock()
	defer s.RUnlock()
	if svcs, ok := s.procsByType[t]; ok {
		return svcs, nil
	}
	return nil, ErrUnknownService
}

func (s *Supervisor) GetByPID(pid int) (Service, error) {
	s.RLock()
	defer s.RUnlock()
	if svc, ok := s.procsByPID[pid]; ok {
		return svc, nil
	}
	return nil, ErrUnknownService
}
