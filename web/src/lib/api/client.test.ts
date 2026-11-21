import type { InternalAxiosRequestConfig } from 'axios';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { api, sendsXsrfToken } from './client';

const request = (method?: string) => ({ method }) as InternalAxiosRequestConfig;

describe('sendsXsrfToken', () => {
  it('leaves the token off requests that only read', () => {
    for (const method of ['get', 'GET', 'head', 'options', undefined]) {
      expect(sendsXsrfToken(request(method))).toBe(false);
    }
  });

  it('sends the token with every request that writes', () => {
    for (const method of ['post', 'put', 'patch', 'delete', 'DELETE']) {
      expect(sendsXsrfToken(request(method))).toBe(true);
    }
  });
});

interface Sent {
  method: string;
  url: string;
  headers: Record<string, string>;
}

/** What went on the wire, in order. */
let sent: Sent[] = [];

/** The least of XMLHttpRequest that axios drives: it records, then answers 200 `{}`. */
class FakeXhr {
  method = '';
  url = '';
  headers: Record<string, string> = {};
  readyState = 0;
  status = 0;
  statusText = '';
  response = '';
  responseText = '';
  responseURL = '';
  responseType = '';
  timeout = 0;
  withCredentials = false;
  onloadend: (() => void) | null = null;
  onabort: (() => void) | null = null;
  onerror: (() => void) | null = null;
  ontimeout: (() => void) | null = null;

  open(method: string, url: string) {
    this.method = method;
    this.url = url;
  }

  setRequestHeader(name: string, value: string) {
    this.headers[name] = value;
  }

  getAllResponseHeaders() {
    return 'content-type: application/json\r\n';
  }

  addEventListener() {}

  abort() {}

  send() {
    sent.push({ method: this.method, url: this.url, headers: this.headers });
    this.readyState = 4;
    this.status = 200;
    this.statusText = 'OK';
    this.response = '{}';
    this.responseText = '{}';
    queueMicrotask(() => this.onloadend?.());
  }
}

describe('the shared client, on the wire', () => {
  beforeEach(() => {
    sent = [];
    document.cookie = 'XSRF-TOKEN=token-from-the-cookie; path=/';
    vi.stubGlobal('XMLHttpRequest', FakeXhr);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    document.cookie = 'XSRF-TOKEN=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT';
  });

  it('is asked to another origin, where a custom header costs a preflight', () => {
    expect(new URL(api.defaults.baseURL ?? '').origin).not.toBe(window.location.origin);
  });

  it('sends a read with Accept alone, so the browser needs no preflight', async () => {
    await api.get('/api/v1/tags');

    expect(sent).toHaveLength(1);
    expect(sent[0].method).toBe('GET');
    expect(Object.keys(sent[0].headers)).toEqual(['Accept']);
  });

  it('still sends the token with a write', async () => {
    await api.post('/api/v1/me/stars', { key: 'entity:1' });
    await api.delete('/api/v1/me/stars/entity:1');

    expect(sent.map((s) => s.method)).toEqual(['POST', 'DELETE']);
    expect(sent[0].headers['X-XSRF-TOKEN']).toBe('token-from-the-cookie');
    expect(sent[0].headers['Content-Type']).toBe('application/json');
    expect(sent[1].headers['X-XSRF-TOKEN']).toBe('token-from-the-cookie');
  });
});
