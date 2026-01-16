// Copyright (c) 2025 Canonical Ltd
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

package httpproxy

import (
	"fmt"
	"math/rand/v2"
	"net/url"
	"slices"
	"sync"

	"github.com/rs/zerolog/log"
)

const (
	// Maximum consecutive failures before marking a URL as unreliable
	maxConsecutiveFailures = 5
	// Probability of selecting from reliable set (95%)
	reliableSelectionProbability = 0.95
)

// urlStats tracks statistics for a single URL
type urlStats struct {
	url                 *url.URL
	consecutiveFailures int
}

// URLTracker manages reliable and unreliable URLs for the proxy
type URLTracker struct {
	reliable   map[string]*urlStats
	unreliable map[string]*urlStats
	mu         sync.RWMutex
}

// NewURLTracker creates a new URL tracker with all URLs initially marked as reliable
func NewURLTracker(targets []*url.URL) (*URLTracker, error) {
	if len(targets) == 0 {
		return nil, fmt.Errorf("cannot create Tracker: no targets provided")
	}

	tracker := &URLTracker{
		reliable:   make(map[string]*urlStats),
		unreliable: make(map[string]*urlStats),
	}

	for _, target := range targets {
		key := target.String()
		tracker.reliable[key] = &urlStats{
			url:                 target,
			consecutiveFailures: 0,
		}
	}

	return tracker, nil
}

// SelectURL picks a URL based on reliability: 95% from reliable set, 5% from unreliable,
// allowing the caller to exclude specific URLs for this selection via butNot.
func (t *URLTracker) SelectURL(butNot []string) *url.URL {
	t.mu.RLock()
	defer t.mu.RUnlock()

	// If no reliable URLs, must use unreliable.
	if len(t.reliable) == 0 {
		log.Warn().Msg("No reliable URLs available, selecting from unreliable set.")

		return t.selectFromUnreliable(butNot, false)
	}

	if len(t.unreliable) == 0 {
		return t.selectFromReliable(butNot, false)
	}

	// 95% chance to select from reliable, 5% from unreliable
	// #nosec G404 -- non-cryptographic random selection
	if rand.Float64() < reliableSelectionProbability {
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
		log.Info().
			Str("url", key).
			Msg("URL moved to reliable set after successful request")

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
		if stats.consecutiveFailures >= maxConsecutiveFailures {
			t.unreliable[key] = stats
			delete(t.reliable, key)
			log.Warn().
				Str("url", key).
				Int("consecutive_failures", stats.consecutiveFailures).
				Msg("URL moved to unreliable set after consecutive failures")
		}
	}

	// If an unreliable URL failed, no actions.
}
