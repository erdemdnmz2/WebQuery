import React, { useEffect, useMemo, useState } from 'react';
import {
  ArrowClockwiseIcon,
  CaretRightIcon,
  DatabaseIcon,
  FloppyDiskIcon,
  LockKeyIcon,
  MagnifyingGlassIcon,
  TableIcon,
  WarningCircleIcon,
} from '@phosphor-icons/react';
import { api, errorMessage } from '../../../services/api';
import { cn } from '../../../lib/cn';
import { formatCount } from '../../../lib/format';
import { Badge, Identifier } from '../../ui/Badge';
import { Button, IconButton } from '../../ui/Button';
import { Checkbox } from '../../ui/Checkbox';
import { EmptyState } from '../../ui/EmptyState';
import { Field } from '../../ui/Field';
import { Input } from '../../ui/Input';
import { Panel, PanelHeader } from '../../ui/Panel';
import { Skeleton } from '../../ui/Skeleton';
import { useToast } from '../../ui/Toast';
import { TIER_LABEL, connectionModeMeta, tiersOf } from '../../../lib/capability';
import type { DatabaseSchema, MaskingRule, RegisteredDatabase } from '../../../types';

const key = (table: string, column: string) =>
  `${table.toLocaleLowerCase('tr')}.${column.toLocaleLowerCase('tr')}`;

export const MaskingTab: React.FC = () => {
  const toast = useToast();

  const [databases, setDatabases] = useState<RegisteredDatabase[]>([]);
  const [loadingDatabases, setLoadingDatabases] = useState(true);
  const [selected, setSelected] = useState<RegisteredDatabase | null>(null);

  const [schema, setSchema] = useState<DatabaseSchema>({});
  const [schemaError, setSchemaError] = useState<string | null>(null);
  const [loadingSchema, setLoadingSchema] = useState(false);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [masked, setMasked] = useState<Set<string>>(new Set());
  const [savedMasked, setSavedMasked] = useState<Set<string>>(new Set());
  const [saving, setSaving] = useState(false);
  const [filter, setFilter] = useState('');

  const loadDatabases = async () => {
    setLoadingDatabases(true);
    try {
      setDatabases(await api.registeredDatabases());
    } catch (caught) {
      toast.error('Veritabanı listesi alınamadı', errorMessage(caught));
    } finally {
      setLoadingDatabases(false);
    }
  };

  useEffect(() => {
    void loadDatabases();
    // Loaded once when the tab mounts.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const loadSchemaAndRules = async (database: RegisteredDatabase) => {
    setLoadingSchema(true);
    setSchemaError(null);
    setSchema({});
    setExpanded({});
    try {
      const [discovered, rules] = await Promise.all([
        api.discoverSchema(database.id),
        api.databaseMaskingRules(database.id),
      ]);
      setSchema(discovered ?? {});
      const active = new Set(
        (rules ?? []).filter((rule) => rule.is_active).map((rule) => key(rule.table_name, rule.column_name)),
      );
      setMasked(active);
      setSavedMasked(new Set(active));
    } catch (caught) {
      setSchemaError(errorMessage(caught));
    } finally {
      setLoadingSchema(false);
    }
  };

  const selectDatabase = (database: RegisteredDatabase) => {
    setSelected(database);
    setFilter('');
    void loadSchemaAndRules(database);
  };

  const saveRules = async () => {
    if (!selected) return;
    setSaving(true);
    const rules: MaskingRule[] = [];
    for (const [table, columns] of Object.entries(schema)) {
      for (const column of columns) {
        if (masked.has(key(table, column))) {
          rules.push({ table_name: table, column_name: column, masking_type: 'default', is_active: true });
        }
      }
    }
    try {
      await api.saveMaskingRules(selected.id, rules);
      setSavedMasked(new Set(masked));
      toast.success('Maskeleme kuralları kaydedildi', `${formatCount(rules.length)} kolon maskeleniyor`);
    } catch (caught) {
      toast.error('Kurallar kaydedilemedi', errorMessage(caught));
    } finally {
      setSaving(false);
    }
  };

  const toggleColumn = (table: string, column: string) => {
    setMasked((current) => {
      const next = new Set(current);
      const id = key(table, column);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleTable = (table: string, columns: string[], checked: boolean) => {
    setMasked((current) => {
      const next = new Set(current);
      for (const column of columns) {
        if (checked) next.add(key(table, column));
        else next.delete(key(table, column));
      }
      return next;
    });
  };

  const visibleTables = useMemo(() => {
    const needle = filter.trim().toLocaleLowerCase('tr');
    const entries = Object.entries(schema);
    if (!needle) return entries;
    return entries
      .map(([table, columns]) => {
        if (table.toLocaleLowerCase('tr').includes(needle)) return [table, columns] as [string, string[]];
        const matched = columns.filter((column) => column.toLocaleLowerCase('tr').includes(needle));
        return matched.length > 0 ? ([table, matched] as [string, string[]]) : null;
      })
      .filter((entry): entry is [string, string[]] => entry !== null);
  }, [schema, filter]);

  const dirty = useMemo(() => {
    if (masked.size !== savedMasked.size) return true;
    for (const id of masked) if (!savedMasked.has(id)) return true;
    return false;
  }, [masked, savedMasked]);

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
      <div className="flex flex-col gap-4 lg:col-span-5">
        <Panel flush as="section" className="flex min-h-0 flex-col">
          <PanelHeader
            title="Kayıtlı veritabanları"
            description={loadingDatabases ? undefined : `${formatCount(databases.length)} kayıt`}
            actions={
              <IconButton label="Listeyi yenile" size="sm" onClick={() => void loadDatabases()}>
                <ArrowClockwiseIcon size={14} className={cn(loadingDatabases && 'animate-spin-slow')} />
              </IconButton>
            }
          />

          {loadingDatabases && databases.length === 0 ? (
            <div className="flex flex-col gap-2 p-4">
              {Array.from({ length: 3 }).map((_, index) => (
                <Skeleton key={index} className="h-11 w-full rounded-sm" />
              ))}
            </div>
          ) : databases.length === 0 ? (
            <EmptyState
              size="sm"
              icon={<DatabaseIcon size={18} />}
              title="Kayıtlı veritabanı yok"
              description="Hedef veritabanı kaydı platform OWNER tarafından yapılır."
            />
          ) : (
            <ul className="max-h-[380px] overflow-y-auto p-1.5">
              {databases.map((database) => {
                const active = selected?.id === database.id;
                return (
                  <li key={database.id}>
                    <button
                      type="button"
                      aria-current={active}
                      onClick={() => selectDatabase(database)}
                      className={cn(
                        'flex w-full items-center gap-3 rounded-sm px-2.5 py-2 text-left',
                        'transition-colors duration-[var(--dur-fast)] hover:bg-hover',
                        active && 'bg-selected hover:bg-selected',
                      )}
                    >
                      <DatabaseIcon size={15} className={cn('shrink-0', active ? 'text-accent' : 'text-subtle')} />
                      <span className="min-w-0 flex-1">
                        <span
                          className={cn(
                            'block truncate font-mono text-[12.5px]',
                            active ? 'text-accent' : 'text-fg',
                          )}
                        >
                          {database.database_name}
                        </span>
                        <span className="block truncate text-[11.5px] text-subtle">{database.servername}</span>
                      </span>
                      <Badge tone="neutral" mono>
                        {database.technology.toLocaleUpperCase('tr')}
                      </Badge>
                      <Badge tone={connectionModeMeta(database.connection_mode).tone}>
                        {connectionModeMeta(database.connection_mode).label}
                      </Badge>
                      <CaretRightIcon
                        size={13}
                        className={cn('shrink-0', active ? 'text-accent' : 'text-faint')}
                      />
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </Panel>
      </div>

      <div className="lg:col-span-7">
        {!selected ? (
          <Panel className="flex h-full min-h-[420px] items-center justify-center">
            <EmptyState
              icon={<LockKeyIcon size={18} />}
              title="Maskeleme kuralları"
              description="Soldaki listeden bir veritabanı seçin. Şeması taranır ve kolon kolon maskeleme kuralı tanımlayabilirsiniz."
            />
          </Panel>
        ) : (
          <Panel flush as="section" className="flex h-full min-h-[420px] flex-col">
            <PanelHeader
              title={
                <span className="font-mono">
                  {selected.database_name}
                  <span className="ml-2 font-sans text-[12px] font-normal text-subtle">{selected.servername}</span>
                </span>
              }
              description={`${formatCount(masked.size)} kolon maskeleniyor`}
              actions={
                <IconButton
                  label="Şemayı yeniden tara"
                  size="sm"
                  onClick={() => void loadSchemaAndRules(selected)}
                >
                  <ArrowClockwiseIcon size={14} className={cn(loadingSchema && 'animate-spin-slow')} />
                </IconButton>
              }
            />

            {/*
              Admin-only breakdown. The SQL editor shows one capability badge
              and nothing else; here the person who registered the database
              needs to see which tiers it actually provisions, because that is
              what bounds every grant made against it.
            */}
            <div className="flex flex-wrap items-center gap-x-3 gap-y-2 border-b border-line px-3 py-2.5">
              <Badge tone={connectionModeMeta(selected.connection_mode).tone}>
                {connectionModeMeta(selected.connection_mode).label}
              </Badge>
              {tiersOf(selected.connection_mode).length === 0 ? (
                <span className="text-[12px] text-subtle">
                  {connectionModeMeta(selected.connection_mode).hint}
                </span>
              ) : (
                <ul className="flex flex-wrap items-center gap-x-3 gap-y-1">
                  {tiersOf(selected.connection_mode).map((tier) => (
                    <li key={tier} className="flex items-center gap-1.5 text-[12px] text-subtle">
                      <Identifier>{tier}</Identifier>
                      {TIER_LABEL[tier]}
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className="border-b border-line px-3 py-2">
              <Field label="Tablo veya kolon ara" className="[&>div:first-child]:sr-only">
                <Input
                  type="search"
                  value={filter}
                  onChange={(event) => setFilter(event.target.value)}
                  placeholder="Tablo veya kolon ara"
                  icon={<MagnifyingGlassIcon size={14} />}
                  disabled={loadingSchema || Object.keys(schema).length === 0}
                />
              </Field>
            </div>

            <div className="min-h-0 flex-1 overflow-y-auto bg-sunken p-2">
              {loadingSchema ? (
                <div className="flex flex-col gap-2 p-2">
                  {Array.from({ length: 6 }).map((_, index) => (
                    <Skeleton key={index} className="h-9 w-full rounded-sm" />
                  ))}
                </div>
              ) : schemaError ? (
                <EmptyState
                  icon={<WarningCircleIcon size={18} />}
                  title="Şema okunamadı"
                  description={schemaError}
                  action={<Button onClick={() => void loadSchemaAndRules(selected)}>Yeniden dene</Button>}
                />
              ) : visibleTables.length === 0 ? (
                <EmptyState
                  size="sm"
                  icon={<TableIcon size={18} />}
                  title={filter ? 'Eşleşen tablo yok' : 'Tablo bulunamadı'}
                  description={
                    filter
                      ? 'Arama terimini kısaltmayı deneyin.'
                      : 'Bu veritabanına bağlanılamadı veya görünür tablo yok. Sunucu erişimini kontrol edin.'
                  }
                />
              ) : (
                <ul className="flex flex-col gap-1">
                  {visibleTables.map(([table, columns]) => {
                    const isOpen = expanded[table] ?? Boolean(filter);
                    const maskedInTable = columns.filter((column) => masked.has(key(table, column))).length;
                    const allMasked = maskedInTable === columns.length && columns.length > 0;

                    return (
                      <li key={table} className="overflow-hidden rounded-sm border border-line bg-surface">
                        <div className="flex items-center gap-2 px-2.5 py-2">
                          <Checkbox
                            checked={allMasked ? true : maskedInTable > 0 ? 'indeterminate' : false}
                            onCheckedChange={(checked) => toggleTable(table, columns, checked)}
                            ariaLabel={`${table} tablosundaki tüm kolonları maskele`}
                          />
                          <button
                            type="button"
                            aria-expanded={isOpen}
                            onClick={() => setExpanded((state) => ({ ...state, [table]: !isOpen }))}
                            className="flex min-w-0 flex-1 items-center gap-2 text-left"
                          >
                            <CaretRightIcon
                              size={12}
                              weight="bold"
                              className={cn(
                                'shrink-0 text-subtle transition-transform duration-[var(--dur-fast)]',
                                isOpen && 'rotate-90',
                              )}
                            />
                            <span className="truncate font-mono text-[12.5px] text-fg">{table}</span>
                            <span className="ml-auto shrink-0 text-[11.5px] text-subtle">
                              {maskedInTable > 0 && (
                                <span className="mr-2 text-warning">{maskedInTable} maskeli</span>
                              )}
                              {columns.length} kolon
                            </span>
                          </button>
                        </div>

                        {isOpen && (
                          <ul className="border-t border-line bg-sunken py-1">
                            {columns.map((column) => {
                              const isMasked = masked.has(key(table, column));
                              return (
                                <li key={column}>
                                  <label
                                    className={cn(
                                      'flex cursor-pointer items-center gap-2 py-1.5 pl-8 pr-3',
                                      'transition-colors duration-[var(--dur-fast)] hover:bg-hover',
                                    )}
                                  >
                                    <Checkbox
                                      checked={isMasked}
                                      onCheckedChange={() => toggleColumn(table, column)}
                                      ariaLabel={`${table}.${column} kolonunu maskele`}
                                    />
                                    <span
                                      className={cn(
                                        'truncate font-mono text-[12px]',
                                        isMasked ? 'text-warning' : 'text-muted',
                                      )}
                                    >
                                      {column}
                                    </span>
                                    {isMasked && (
                                      <LockKeyIcon size={12} weight="fill" className="ml-auto text-warning" />
                                    )}
                                  </label>
                                </li>
                              );
                            })}
                          </ul>
                        )}
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>

            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line px-4 py-3">
              <p className="text-[12.5px] text-subtle">
                {dirty ? (
                  <span className="text-warning">Kaydedilmemiş değişiklik var</span>
                ) : (
                  'Tüm değişiklikler kaydedildi'
                )}
              </p>
              <Button
                variant="primary"
                icon={<FloppyDiskIcon size={14} />}
                loading={saving}
                disabled={!dirty || loadingSchema}
                onClick={() => void saveRules()}
              >
                Kuralları kaydet
              </Button>
            </div>
          </Panel>
        )}
      </div>
    </div>
  );
};
