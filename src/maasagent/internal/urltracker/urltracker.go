// Copyright (c) 2025-2026 Canonical Ltd
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

package urltracker

import (
	"fmt"
	"log/slog"
	"math/rand/v2"
	"net/url"
	"slices"
	"sync"

	"maas.io/core/src/maasagent/internal/logger"
)

const (
	// Maximum consecutive failures before marking a URL as unreliable
	defaultMaxConsecutiveFailures = 5
	// Probability of selecting from reliable set (95%)
	defaultReliableSelectionProbability = 0.95
)

// URLStats tracks statistics for a single URL
type URLStats struct {
	url                 *url.URL
	consecutiveFailures int
}

// URLTracker manages reliable and unreliable URLs for the proxy
type URLTracker struct {
	logger                       *slog.Logger
	reliable                     map[string]*URLStats
	unreliable                   map[string]*URLStats
	maxConsecutiveFailures       int
	reliableSelectionProbability float64
	mu                           sync.RWMutex
}

// New creates a new URL tracker with all URLs initially marked as reliable
func New(targets []*url.URL, opts ...Option) (*URLTracker, error) {
	if len(targets) == 0 {
		return nil, fmt.Errorf("cannot create Tracker: no targets provided")
	}

	tracker := &URLTracker{
		logger:                       logger.Noop(),
		maxConsecutiveFailures:       defaultMaxConsecutiveFailures,
		reliableSelectionProbability: defaultReliableSelectionProbability,
		reliable:                     make(map[string]*URLStats),
		unreliable:                   make(map[string]*URLStats),
	}

	for _, target := range targets {
		key := target.String()
		tracker.reliable[key] = &URLStats{
			url:                 target,
			consecutiveFailures: 0,
		}
	}

	for _, opt := range opts {
		opt(tracker)
	}

	return tracker, nil
}

type Option func(*URLTracker)

// WithLogger allows setting custom logger. By default logger is no-op.
func WithLogger(l *slog.Logger) Option {
	return func(t *URLTracker) {
		if l != nil {
			t.logger = l
		}
	}
}

func WithMaxConsecutiveFailures(i int) Option {
	return func(t *URLTracker) {
		t.maxConsecutiveFailures = i
	}
}

// SelectURL picks a URL based on reliability: 95% from reliable set, 5% from unreliable,
// allowing the caller to exclude specific URLs for this selection via butNot.
func (t *URLTracker) SelectURL(butNot []string) *url.URL {
	t.mu.RLock()
	defer t.mu.RUnlock()

	// If no reliable URLs, must use unreliable.
	if len(t.reliable) == 0 {
		t.logger.Warn("No reliable URLs available, selecting from unreliable set.")

		return t.selectFromUnreliable(butNot, false)
	}

	if len(t.unreliable) == 0 {
		return t.selectFromReliable(butNot, false)
	}

	// 95% chance to select from reliable, 5% from unreliable
	// #nosec G404 -- non-cryptographic random selection
	if rand.Float64() < t.reliableSelectionProbability {
		return t.selectFromReliable(butNot, true)
	}

	return t.selectFromUnreliable(butNot, true)
}

// selectFromUnreliable picks a random URL from the unreliable set, excluding any in butNot. If all are excluded,
// falls back to reliable.
func (t *URLTracker) selectFromUnreliable(butNot []string, fallbackToReliable bool) *url.URL {
	for candidateURL := range t.unreliable {
		if !slices.Contains(butNot, candidateURL) {
			return t.unreliable[candidateURL].url
		}
	}

	// Fallback to reliable if all unreliable are excluded
	if fallbackToReliable {
		return t.selectFromReliable(butNot, false)
	}

	return nil
}

// selectFromReliable picks a random URL from the reliable set, excluding any in butNot. If all are excluded, falls back to unreliable.
func (t *URLTracker) selectFromReliable(butNot []string, fallbackToUnreliable bool) *url.URL {
	for candidateURL := range t.reliable {
		if !slices.Contains(butNot, candidateURL) {
			return t.reliable[candidateURL].url
		}
	}

	// Fallback to unreliable if all reliable are excluded
	if fallbackToUnreliable {
		return t.selectFromUnreliable(butNot, false)
	}

	return nil
}

// RecordSuccess marks a successful request for a URL
func (t *URLTracker) RecordSuccess(target *url.URL) {
	t.mu.Lock()
	defer t.mu.Unlock()

	key := target.String()

	// If it was in unreliable, move to reliable
	if stats, exists := t.unreliable[key]; exists {
		stats.consecutiveFailures = 0
		t.reliable[key] = stats
		delete(t.unreliable, key)
		t.logger.Info("URL moved to reliable set after successful request",
			slog.String("url", key))

		return
	}

	// If in reliable, reset failure count
	if stats, exists := t.reliable[key]; exists {
		stats.consecutiveFailures = 0
	}
}

// RecordFailure marks a failed request for a URL
func (t *URLTracker) RecordFailure(target *url.URL) {
	t.mu.Lock()
	defer t.mu.Unlock()

	key := target.String()

	// Look for the URL in reliable first
	stats, inReliable := t.reliable[key]

	if inReliable {
		stats.consecutiveFailures++
		if stats.consecutiveFailures >= t.maxConsecutiveFailures {
			t.unreliable[key] = stats
			delete(t.reliable, key)
			t.logger.Warn("URL moved to unreliable set after consecutive failures",
				slog.String("url", key),
				slog.Int("consecutive_failures", stats.consecutiveFailures))
		}
	}

	// If an unreliable URL failed, no actions.
}

// ForEachReliable allows the user to iterate over reliable targets
func (t *URLTracker) ForEachReliable(yield func(string, *URLStats) bool) {
	t.mu.RLock()
	defer t.mu.RUnlock()

	for k, v := range t.reliable {
		if !yield(k, v) {
			return
		}
	}
}

// ForEachUnreliable allows the user to iterate over reliable targets
func (t *URLTracker) ForEachUnreliable(yield func(string, *URLStats) bool) {
	t.mu.RLock()
	defer t.mu.RUnlock()

	for k, v := range t.unreliable {
		if !yield(k, v) {
			return
		}
	}
}
