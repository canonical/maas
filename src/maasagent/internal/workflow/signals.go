package workflow

import (
	"errors"
	"fmt"

	"go.temporal.io/sdk/workflow"
)

var (
	// ErrNoLease is an error for when no lease has been reported
	// for the deploying host
	ErrNoLease = errors.New("no lease received")
	// ErrBootAssetsNotRequested is an error for when the deploying host
	// has not requested boot assets
	ErrBootAssetsNotRequested = errors.New("boot assets not requested")
	// ErrCurtinNotDownloaded is an error for when curtin has not been downloaded
	// to the deploying host
	ErrCurtinNotDownloaded = errors.New("curtin was not downloaded")
	// ErrCurtinFailed is an error for when the deploying host's curtin execution
	// has failed
	ErrCurtinFailed = errors.New("curtin did not complete")

	ErrNoTFTPAck = errors.New("did not receive tftp ack")

	ErrCloudInitDidNotStart = errors.New("cloud-init did not start")

	ErrCloudInitFailed = errors.New("cloud-init failed to finished")
)

// Signal is an interface for listening on a signal channel and receiving data
type Signal interface {
	// GetName returns the name of the corresponding signal channel
	GetName(string) string
}

// LeaseSignal is a signal value for leases received
type LeaseSignal struct {
	IP  string
	MAC string
}

// GetName returns leases-<system_id> for a given machine's lease signal
func (l LeaseSignal) GetName(systemID string) string {
	return fmt.Sprintf("leases-%s", systemID)
}

// BootAssetsSignal is a signal value for when a host downloads boot assets
type BootAssetsSignal struct {
	SystemID string
}

// GetName returns the name of a signal channel for a given machine ack'ing
// the request of boot assets via tftp
func (b BootAssetsSignal) GetName(systemID string) string {
	return fmt.Sprintf("tftp-ack-%s", systemID)
}

// CurtinDownloadSignal is a signal value for when curtin has been downloaded
// by a deploying host
type CurtinDownloadSignal struct {
	SystemID string
}

// GetName returns the name of a signal channel for a given machine downloading curtin for execution
func (c CurtinDownloadSignal) GetName(systemID string) string {
	return fmt.Sprintf("curtin-download-%s", systemID)
}

// CurtinFinishedSignal is a signal value for when curtin execution has finished
type CurtinFinishedSignal struct {
	Success bool
}

// GetName returns the name of a signal channel for a given machine's curtin execution finishing
func (c CurtinFinishedSignal) GetName(systemID string) string {
	return fmt.Sprintf("curtin-finished-%s", systemID)
}

// CloudInitStartSignal is a signal value for when cloud-init execution starts
type CloudInitStartSignal struct {
	SystemID string
}

func (c CloudInitStartSignal) GetName(systemID string) string {
	return fmt.Sprintf("cloud-init-start-%s", systemID)
}

type CloudInitFinishedSignal struct {
	SystemID string
}

func (c CloudInitFinishedSignal) GetName(systemID string) string {
	return fmt.Sprintf("cloud-init-end-%s", systemID)
}

func receive[T Signal](ctx workflow.Context, systemID string) T {
	var signal T

	c := workflow.GetSignalChannel(ctx, signal.GetName(systemID))
	c.Receive(ctx, &signal)

	return signal
}
