package cache

import (
	"errors"
	"fmt"
	"io"
)

// Buffer implements io.ReadWriteSeeker for testing purposes.
type Buffer struct {
	buffer []byte
	offset int64
}

// NewBuffer returns buffer that implements io.ReadWriteSeeker
func NewBuffer(initial []byte) Buffer {
	if initial == nil {
		initial = make([]byte, 0, 1024)
	}

	return Buffer{
		buffer: initial,
		offset: 0,
	}
}

func (buf *Buffer) Bytes() []byte {
	return buf.buffer
}

func (buf *Buffer) Len() int {
	return len(buf.buffer)
}

func (buf *Buffer) Read(b []byte) (int, error) {
	available := len(buf.buffer) - int(buf.offset)
	if available == 0 {
		return 0, io.EOF
	}

	size := len(b)
	if size > available {
		size = available
	}

	copy(b, buf.buffer[buf.offset:buf.offset+int64(size)])
	buf.offset += int64(size)

	return size, nil
}

func (buf *Buffer) Write(b []byte) (int, error) {
	copied := copy(buf.buffer[buf.offset:], b)
	if copied < len(b) {
		buf.buffer = append(buf.buffer, b[copied:]...)
	}

	buf.offset += int64(len(b))

	return len(b), nil
}

func (buf *Buffer) Seek(offset int64, whence int) (int64, error) {
	var newOffset int64

	switch whence {
	case io.SeekStart:
		newOffset = offset
	case io.SeekCurrent:
		newOffset = buf.offset + offset
	case io.SeekEnd:
		newOffset = int64(len(buf.buffer)) + offset
	default:
		return 0, errors.New("unknown seek method")
	}

	if newOffset > int64(len(buf.buffer)) || newOffset < 0 {
		return 0, fmt.Errorf("invalid offset %d", offset)
	}

	buf.offset = newOffset

	return newOffset, nil
}

func (buf *Buffer) Close() error {
	// no-op
	return nil
}
