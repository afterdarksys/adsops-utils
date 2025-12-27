package store

import (
	"context"
	"database/sql"
	"fmt"

	_ "github.com/lib/pq"
	"github.com/adsops-utils/internal/config"
)

// Store provides access to all data stores
type Store struct {
	db      *sql.DB
	Tickets *TicketStore
	Projects *ProjectStore
	Groups  *GroupStore
	Repositories *RepositoryStore
	Contacts *ContactStore
	Employees *EmployeeStore
	ACLs    *ACLStore
	Audit   *AuditStore
}

// New creates a new store instance
func New(cfg *config.DatabaseConfig) (*Store, error) {
	db, err := sql.Open("postgres", cfg.DSN())
	if err != nil {
		return nil, fmt.Errorf("failed to open database: %w", err)
	}

	db.SetMaxOpenConns(cfg.MaxOpenConns)
	db.SetMaxIdleConns(cfg.MaxIdleConns)

	// Test connection
	if err := db.Ping(); err != nil {
		return nil, fmt.Errorf("failed to ping database: %w", err)
	}

	s := &Store{db: db}
	s.Tickets = &TicketStore{db: db}
	s.Projects = &ProjectStore{db: db}
	s.Groups = &GroupStore{db: db}
	s.Repositories = &RepositoryStore{db: db}
	s.Contacts = &ContactStore{db: db}
	s.Employees = &EmployeeStore{db: db}
	s.ACLs = &ACLStore{db: db}
	s.Audit = &AuditStore{db: db}

	return s, nil
}

// Close closes the database connection
func (s *Store) Close() error {
	return s.db.Close()
}

// BeginTx starts a new transaction
func (s *Store) BeginTx(ctx context.Context) (*sql.Tx, error) {
	return s.db.BeginTx(ctx, nil)
}

// DB returns the underlying database connection
func (s *Store) DB() *sql.DB {
	return s.db
}

// WithTx executes a function within a transaction
func (s *Store) WithTx(ctx context.Context, fn func(tx *sql.Tx) error) error {
	tx, err := s.BeginTx(ctx)
	if err != nil {
		return err
	}

	if err := fn(tx); err != nil {
		if rbErr := tx.Rollback(); rbErr != nil {
			return fmt.Errorf("tx error: %v, rollback error: %v", err, rbErr)
		}
		return err
	}

	return tx.Commit()
}
