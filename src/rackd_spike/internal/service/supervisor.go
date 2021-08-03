package service

import (
	"context"
	"errors"
	"sync"
)

// an enum of service types
const (
	SvcUnknown = iota
	SvcRack
	SvcDHCP
	SvcDHCP6
	SvcDHCPRelay
	SvcDNS
	SvcNTP
	SvcPROXY
	SvcTFTP
)

var (
	ErrUnknownService        = errors.New("service is not registered with supervisor")
	ErrServiceAlreadyRunning = errors.New("service is already in a running state")
	ErrServiceAlreadyStopped = errors.New("service is already in a stopped state")
	ErrInvalidServiceState   = errors.New("service is in an invalid state for this operation")
	ErrInvalidServiceType    = errors.New("invalid service type for given service")
	ErrUnexpectedServiceExit = errors.New("service exited unexpectedly")
	ErrUnsuccessfulStart     = errors.New("not all services started correctly")
	ErrUnsuccessfulStop      = errors.New("not all services shutdown correctly")
)

// Service is an interface outlining behavior to manage external services
type Service interface {
	Name() string
	Type() int
	PID() int
	Start(context.Context) error
	Stop(context.Context) error
	Restart(context.Context) error
	Status(context.Context) error
}

// ReloadableService is a service that can reload configuration
type ReloadableService interface {
	Service
	Reload(context.Context) error
}

// SvcManager is an interface outlining behavior to manage a group of services
type SvcManager interface {
	// RegisterService adds a given service to SvcManager's set of services
	RegisterService(Service)
	// StartAll starts all managed service
	StartAll(context.Context) error
	// Start starts a service of a given name
	Start(context.Context, string) error
	// StartByType starts all services of a given type
	StartByType(context.Context, int) error
	// StopAll stops all services
	StopAll(context.Context) error
	// Stop stops a given service
	Stop(context.Context, string) error
	// StopByType stops all services of a given type
	StopByType(context.Context, int) error
	// Restart restarts a given service
	Restart(context.Context, string) error
	// RestartByType restarts all services of a given type
	RestartByType(context.Context, int) error
	// Get returns a given service within SvcManager's set of services
	Get(string) (Service, error)
	// GetByType returns all services of a given type
	GetByType(int) ([]Service, error)
	// GetByPID returns a service associated with a given pid
	GetByPID(int) (Service, error)
	// GetSvcCount returns the number of services registered
	GetSvcCount() int
	// GetStatusMap returns the status of the services
	GetStatusMap(ctx context.Context) map[string]string
}

// Supervisor is an implementation of SvcManager
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

func (s *Supervisor) GetSvcCount() int {
	s.RLock()
	defer s.RUnlock()
	return len(s.procsByName)
}

func (s *Supervisor) GetStatusMap(ctx context.Context) (status map[string]string) {
	s.RLock()
	defer s.RUnlock()

	status = make(map[string]string, len(s.procsByName))

	for id, svc := range s.procsByName {
		switch err := svc.Status(ctx); err {
		case nil:
			status[id] = "running"

			// TODO compare expected and current state
		default:
			status[id] = "off"
		}
	}
	return
}
