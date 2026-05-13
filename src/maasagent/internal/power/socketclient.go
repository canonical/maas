// Copyright (c) 2023-2026 Canonical Ltd
//
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU Affero General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU Affero General Public License for more details.
//
// You should have received a copy of the GNU Affero General Public License
// along with this program.  If not, see <http://www.gnu.org/licenses/>.

package power

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log/slog"
	"net"
	"net/http"
	"time"

	"github.com/cenkalti/backoff/v4"
)

// SocketClient communicates with a single power driver over a UNIX domain socket.
// It provides methods for all power actions defined in the driver service protocol.
type SocketClient struct {
	logger     *slog.Logger
	socketPath string
	timeout    time.Duration
}

// NewSocketClient creates a new SocketClient for the given UNIX socket path.
func NewSocketClient(logger *slog.Logger, socketPath string) *SocketClient {
	return &SocketClient{
		logger:     logger,
		socketPath: socketPath,
		timeout:    10 * time.Second,
	}
}

// GetMetadata queries the driver's /metadata endpoint and returns the parsed metadata.
func (c *SocketClient) GetMetadata(ctx context.Context) (map[string]any, error) {
	var metadata map[string]any
	if err := c.doRequest(ctx, http.MethodGet, "/metadata", nil, &metadata); err != nil {
		return nil, err
	}
	return metadata, nil
}

// Query queries the power state of a system via POST /query.
func (c *SocketClient) Query(ctx context.Context, systemID string, context map[string]any) (map[string]any, error) {
	body := map[string]any{
		"system_id": systemID,
		"context":   context,
	}
	var result map[string]any
	if err := c.doRequest(ctx, http.MethodPost, "/query", body, &result); err != nil {
		return nil, err
	}
	return result, nil
}

// On powers on a system via POST /on.
func (c *SocketClient) On(ctx context.Context, systemID string, context map[string]any) (map[string]any, error) {
	body := map[string]any{
		"system_id": systemID,
		"context":   context,
	}
	var result map[string]any
	if err := c.doRequest(ctx, http.MethodPost, "/on", body, &result); err != nil {
		return nil, err
	}
	return result, nil
}

// Off powers off a system via POST /off.
func (c *SocketClient) Off(ctx context.Context, systemID string, context map[string]any) (map[string]any, error) {
	body := map[string]any{
		"system_id": systemID,
		"context":   context,
	}
	var result map[string]any
	if err := c.doRequest(ctx, http.MethodPost, "/off", body, &result); err != nil {
		return nil, err
	}
	return result, nil
}

// Cycle power-cycles a system via POST /cycle.
func (c *SocketClient) Cycle(ctx context.Context, systemID string, context map[string]any) (map[string]any, error) {
	body := map[string]any{
		"system_id": systemID,
		"context":   context,
	}
	var result map[string]any
	if err := c.doRequest(ctx, http.MethodPost, "/cycle", body, &result); err != nil {
		return nil, err
	}
	return result, nil
}

// Reset resets a system via POST /reset.
func (c *SocketClient) Reset(ctx context.Context, systemID string, context map[string]any) (map[string]any, error) {
	body := map[string]any{
		"system_id": systemID,
		"context":   context,
	}
	var result map[string]any
	if err := c.doRequest(ctx, http.MethodPost, "/reset", body, &result); err != nil {
		return nil, err
	}
	return result, nil
}

// SetBootOrder sets the boot order for a system via POST /set-boot-order.
func (c *SocketClient) SetBootOrder(ctx context.Context, systemID string, context map[string]any, order []string) (map[string]any, error) {
	body := map[string]any{
		"system_id": systemID,
		"context":   context,
		"order":     order,
	}
	var result map[string]any
	if err := c.doRequest(ctx, http.MethodPost, "/set-boot-order", body, &result); err != nil {
		return nil, err
	}
	return result, nil
}

// doRequest performs an HTTP request to the driver socket with retry logic.
// It retries on connection errors using exponential backoff.
func (c *SocketClient) doRequest(ctx context.Context, method, path string, reqBody any, respBody any) error {
	var lastErr error

	op := func() error {
		select {
		case <-ctx.Done():
			return backoff.Permanent(ctx.Err())
		default:
		}

		var bodyReader *bytes.Reader
		if reqBody != nil {
			data, err := json.Marshal(reqBody)
			if err != nil {
				return backoff.Permanent(fmt.Errorf("marshal request body: %w", err))
			}
			bodyReader = bytes.NewReader(data)
		}

		addr := "http://localhost" + path
		req, err := http.NewRequestWithContext(ctx, method, addr, bodyReader)
		if err != nil {
			return backoff.Permanent(fmt.Errorf("create request: %w", err))
		}

		if reqBody != nil {
			req.Header.Set("Content-Type", "application/json")
		}

		client := &http.Client{
			Timeout: c.timeout,
			Transport: &http.Transport{
				DialContext: func(ctx context.Context, _, _ string) (net.Conn, error) {
					return net.DialTimeout("unix", c.socketPath, c.timeout)
				},
			},
		}

		resp, err := client.Do(req)
		if err != nil {
			var netErr net.Error
			if errors.As(err, &netErr) && netErr.Timeout() {
				return fmt.Errorf("request timed out: %w", err)
			}
			lastErr = &PowerConnError{
				SocketPath: c.socketPath,
				Op:         method + " " + path,
				Err:        err,
			}
			return lastErr
		}
		defer resp.Body.Close()

		if resp.StatusCode != http.StatusOK {
			respData, _ := io.ReadAll(resp.Body)
			lastErr = &PowerActionError{
				SocketPath:   c.socketPath,
				Op:           method + " " + path,
				StatusCode:   resp.StatusCode,
				ResponseBody: string(respData),
			}
			return backoff.Permanent(lastErr)
		}

		if respBody != nil {
			if err := json.NewDecoder(resp.Body).Decode(respBody); err != nil {
				return backoff.Permanent(fmt.Errorf("decode response: %w", err))
			}
		}

		return nil
	}

	b := backoff.NewExponentialBackOff()
	b.MaxElapsedTime = 5 * time.Second
	b.MaxInterval = 1 * time.Second

	err := backoff.RetryNotify(op, b, func(err error, delay time.Duration) {
		c.logger.Debug("retrying power driver request", "error", err, "delay", delay)
	})

	if err != nil {
		if errors.Is(err, context.DeadlineExceeded) || errors.Is(err, context.Canceled) {
			return &PowerConnError{
				SocketPath: c.socketPath,
				Op:         method + " " + path,
				Err:        err,
			}
		}
		if lastErr != nil {
			return lastErr
		}
		return &PowerConnError{
			SocketPath: c.socketPath,
			Op:         method + " " + path,
			Err:        err,
		}
	}

	return nil
}

// PowerConnError is returned when a connection to a driver socket fails.
type PowerConnError struct {
	SocketPath string
	Op         string
	Err        error
}

func (e *PowerConnError) Error() string {
	return fmt.Sprintf("power driver connection error on %s (%s): %v", e.SocketPath, e.Op, e.Err)
}

func (e *PowerConnError) Unwrap() error {
	return e.Err
}

// PowerActionError is returned when a driver returns a non-200 HTTP status.
type PowerActionError struct {
	SocketPath   string
	Op           string
	StatusCode   int
	ResponseBody string
}

func (e *PowerActionError) Error() string {
	return fmt.Sprintf("power driver action error on %s (%s): status %d: %s", e.SocketPath, e.Op, e.StatusCode, e.ResponseBody)
}
