package power

import (
	"context"
	"errors"
	"fmt"
	"net"
	"sync"
)

const (
	ConfigTypeUnknown = iota
	ConfigTypeString
	ConfigTypeMACAddress
	ConfigTypeChoice
	ConfigTypePassword
)

const (
	ConfigScopeBMC = iota
	ConfigScopeNode
)

var (
	ErrFieldAlreadyDefined  = errors.New("the given field is already defined")
	ErrTooManyOptionalAttrs = errors.New("too many optional attributes, only one set of optional attributes to a given field may be provied")
	ErrMustBeTypeChoice     = errors.New("choices can only be provided for a field of type choice")
	ErrFieldNotFound        = errors.New("the given field is not found in the given config")
	ErrFieldWrongType       = errors.New("the given field is of a different type than requested")
	ErrInvalidChoice        = errors.New("invalid choice provided")
	ErrInvalidType          = errors.New("the given field is defined with an invalid type")
)

type powerConfigField struct {
	Key      string
	Val      string
	Required bool
	Default  string
	Type     int
	Choices  map[string]string
	Scope    int
}

func (p powerConfigField) ValOrDefault() string {
	if len(p.Val) > 0 {
		return p.Val
	}
	return p.Default
}

type OptionalFieldAttrs struct {
	Default string
	Choices map[string]string
	Scope   int
}

type PowerConfig struct {
	sync.RWMutex
	cfg map[string]powerConfigField
}

func (p *PowerConfig) CreateField(name string, fieldType int, required bool, optional ...OptionalFieldAttrs) error {
	p.Lock()
	defer p.Unlock()

	if p.cfg == nil {
		p.cfg = make(map[string]powerConfigField)
	}

	if _, ok := p.cfg[name]; ok {
		return fmt.Errorf("%w: %s", ErrFieldAlreadyDefined, name)
	}
	if len(optional) > 1 {
		return ErrTooManyOptionalAttrs
	}

	field := powerConfigField{
		Key:      name,
		Type:     fieldType,
		Required: required,
	}
	if len(optional) == 1 {
		field.Default = optional[0].Default
		field.Scope = optional[0].Scope
		if optional[0].Choices != nil {
			if field.Type != ConfigTypeChoice {
				return fmt.Errorf("%w: %s", ErrMustBeTypeChoice, name)
			}
			field.Choices = optional[0].Choices
		}
	}

	p.cfg[name] = field
	return nil
}

func (p *PowerConfig) Get(name string) (string, error) {
	p.RLock()
	defer p.RUnlock()

	field, ok := p.cfg[name]
	if !ok {
		return "", fmt.Errorf("%w: %s", ErrFieldNotFound, name)
	}
	return field.ValOrDefault(), nil
}

func (p *PowerConfig) Set(name, val string) error {
	p.Lock()
	defer p.Unlock()

	field, ok := p.cfg[name]
	if !ok {
		return fmt.Errorf("%w: %s", ErrFieldNotFound, name)
	}
	switch field.Type {
	case ConfigTypeString:
		field.Val = val
	case ConfigTypeChoice:
		_, ok := field.Choices[val]
		if !ok {
			return fmt.Errorf("%w: %s is an invalid choice for %s", ErrInvalidChoice, val, name)
		}
		field.Val = val
	case ConfigTypeMACAddress:
		_, err := net.ParseMAC(val)
		if err != nil {
			return err
		}
		field.Val = val
	case ConfigTypePassword:
		field.Val = val
	default:
		return fmt.Errorf("%w: %s", ErrInvalidType, name)
	}
	p.cfg[name] = field
	return nil
}

func (p *PowerConfig) GetMAC(name string) (net.HardwareAddr, error) {
	field, ok := p.cfg[name]
	if !ok {
		return nil, fmt.Errorf("%w: %s", ErrFieldNotFound, name)
	}
	if field.Type != ConfigTypeMACAddress {
		return nil, fmt.Errorf("%w: %s is not of type MAC Address", ErrFieldWrongType, name)
	}
	return net.ParseMAC(field.ValOrDefault())
}

func (p *PowerConfig) GetChoice(name string) (string, error) {
	field, ok := p.cfg[name]
	if !ok {
		return "", fmt.Errorf("%w: %s", ErrFieldNotFound, name)
	}
	if field.Type != ConfigTypeChoice {
		return "", fmt.Errorf("%w: %s is not of type Choice", ErrFieldWrongType, name)
	}
	return field.Choices[field.ValOrDefault()], nil
}

func (p *PowerConfig) GetPassword(name string) (string, error) {
	field, ok := p.cfg[name]
	if !ok {
		return "", fmt.Errorf("%w: %s", ErrFieldNotFound, name)
	}
	if field.Type != ConfigTypePassword {
		return "", fmt.Errorf("%w: %s is not of type Password", ErrFieldWrongType, name)
	}
	return field.ValOrDefault(), nil
}

type PowerDriver interface {
	Name() string
	Description() string
	Settings() PowerConfig
	IPExactor() (string, string)
	Queryable() bool
	Chassis() bool
	CanProbe() bool
	CanSetBootOrder() bool
	DetectMissingPackages() error
	Schema() map[string]interface{}
	GetSetting(string) (string, error)
	PowerOn(context.Context, string, PowerConfig) error
	PowerOff(context.Context, string, PowerConfig) error
	PowerCycle(context.Context, string, PowerConfig) error
	PowerQuery(context.Context, string, PowerConfig) (string, error)
}

type OrderableBootPowerDriver interface {
	PowerDriver
	SetBootOrder(context.Context, string, PowerConfig, []string)
}
